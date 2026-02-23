"""Deterministic DAG orchestrator with bounded workflows."""

import hashlib
import json
import time
from typing import Any, Dict, List

from services.belief.schemas import BeliefRequest
from services.belief.service import BeliefEngine
from services.contradiction.schemas import AnalysisRequest
from services.contradiction.relation_engine import EpistemicRelationEngine
from services.extraction.schemas import ClaimExtractionRequest
from services.extraction.service import ClaimExtractor
from services.ingestion.schemas import IngestionRequest
from services.ingestion.service import IngestionService
from services.normalization.schemas import NormalizationRequest
from services.normalization.service import NormalizationService
from services.orchestrator.schemas import (
    ExecutionLog,
    Task,
    TaskResult,
    Workflow,
    WorkflowRequest,
    WorkflowResult,
)
from services.orchestrator.workflows import WORKFLOWS


class Orchestrator:
    """
    Deterministic DAG orchestrator.

    Executes pre-defined bounded workflows with topological ordering.
    No dynamic planning, no LLM-driven routing.
    All execution paths are explicit and inspectable.
    """

    def __init__(self):
        """Initialize orchestrator with service instances."""
        self.ingestion = IngestionService()
        self.extraction = ClaimExtractor()
        self.normalization = NormalizationService()
        self.relation_engine = EpistemicRelationEngine()
        self.belief = BeliefEngine()

    def execute_workflow(self, request: WorkflowRequest) -> WorkflowResult:
        """
        Execute a deterministic workflow.

        Args:
            request: WorkflowRequest with workflow_id and input_data

        Returns:
            WorkflowResult with final output and execution logs

        Raises:
            ValueError: If workflow_id is not found
        """
        # Retrieve workflow definition
        workflow = WORKFLOWS.get(request.workflow_id)
        if not workflow:
            raise ValueError(f"Unknown workflow_id: {request.workflow_id}")

        # Execute tasks in topological order
        task_outputs: Dict[str, Any] = {}
        execution_logs: List[ExecutionLog] = []
        start_time = time.time()

        for task in workflow.tasks:
            result = self._execute_task(task, task_outputs, request.input_data)
            task_outputs[task.task_id] = result.output
            execution_logs.append(result.log)

        total_latency_ms = (time.time() - start_time) * 1000

        # Final output is the last task's output
        final_task_id = workflow.tasks[-1].task_id
        final_output = task_outputs[final_task_id]

        return WorkflowResult(
            workflow_id=request.workflow_id,
            final_output=final_output,
            execution_logs=execution_logs,
            total_latency_ms=total_latency_ms,
        )

    def _execute_task(
        self, task: Task, task_outputs: Dict[str, Any], initial_input: Dict[str, Any]
    ) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task definition
            task_outputs: Dictionary of outputs from completed tasks
            initial_input: Initial workflow input data

        Returns:
            TaskResult with output and execution log
        """
        start_time = time.time()

        # Resolve input from dependencies or initial input
        if task.dependencies:
            # Use output from first dependency as input
            input_data = task_outputs[task.dependencies[0]]
        else:
            # Use initial input
            input_data = initial_input

        # Execute component
        output = self._execute_component(task.component, input_data)

        latency_ms = (time.time() - start_time) * 1000

        # Generate execution log
        log = ExecutionLog(
            task_id=task.task_id,
            component=task.component,
            input_hash=self._hash_data(input_data),
            output_hash=self._hash_data(output),
            latency_ms=latency_ms,
            deterministic=True,
        )

        return TaskResult(task_id=task.task_id, output=output, log=log)

    def _execute_component(self, component: str, input_data: Any) -> Any:
        """
        Execute a specific component.

        Args:
            component: Component name
            input_data: Input data for the component

        Returns:
            Component output

        Raises:
            ValueError: If component is unknown
        """
        if component == "ingestion":
            # Map simple text input to IngestionRequest schema
            if "text" in input_data and "raw_text" not in input_data:
                input_data = {
                    "source_id": input_data.get("source_id", "orchestrator_input"),
                    "raw_text": input_data["text"],
                }
            request = IngestionRequest(**input_data)
            result = self.ingestion.ingest_text(request)
            return {"chunks": [chunk.model_dump() for chunk in result.chunks]}

        elif component == "extraction":
            # Input is ingestion output
            from services.ingestion.schemas import IngestionChunk

            chunks_data = input_data.get("chunks", [])
            # Extract from all chunks
            all_claims = []
            for chunk_data in chunks_data:
                # Reconstruct IngestionChunk
                chunk = IngestionChunk(**chunk_data)
                extract_req = ClaimExtractionRequest(chunk=chunk)
                extract_result = self.extraction.extract(extract_req)
                if extract_result.claim:
                    all_claims.append(extract_result.claim.model_dump())
            return {"claims": all_claims}

        elif component == "normalization":
            # Input is extraction output
            claims_data = input_data.get("claims", [])
            normalized_claims = []
            for claim_data in claims_data:
                # Reconstruct Claim from dict
                from core.schemas.claim import Claim

                claim = Claim(**claim_data)
                norm_req = NormalizationRequest(claim=claim)
                norm_result = self.normalization.normalize(norm_req)
                if norm_result.normalized:
                    normalized_claims.append(norm_result.normalized.model_dump())
            return {"normalized_claims": normalized_claims}

        elif component == "contradiction":
            # Input is normalization output
            from services.normalization.schemas import NormalizedClaim

            normalized_data = input_data.get("normalized_claims", [])
            normalized_claims = [NormalizedClaim(**nc) for nc in normalized_data]
            contra_req = AnalysisRequest(claims=normalized_claims)
            relation_graph = self.relation_engine.analyze(contra_req)
            return {
                "contradictions": [c.model_dump() for c in relation_graph.contradictions],
                "performance_variance": [
                    pv.model_dump() for pv in relation_graph.performance_variance
                ],
                "divergences": [d.model_dump() for d in relation_graph.conditional_divergences],
                "normalized_claims": normalized_data,
            }

        elif component == "belief":
            # Input is contradiction output (epistemic relation graph)
            from services.normalization.schemas import NormalizedClaim
            from services.contradiction.epistemic_relations import Contradiction

            normalized_data = input_data.get("normalized_claims", [])
            contradiction_data = input_data.get("contradictions", [])
            divergences_data = input_data.get("divergences", [])
            performance_variance_data = input_data.get("performance_variance", [])
            
            normalized_claims = [NormalizedClaim(**nc) for nc in normalized_data]
            contradictions = [Contradiction(**c) for c in contradiction_data]
            
            belief_req = BeliefRequest(
                normalized_claims=normalized_claims,
                contradictions=contradictions,
            )
            belief_states = self.belief.compute_beliefs(belief_req)
            return {
                "belief_states": [bs.model_dump() for bs in belief_states],
                "divergences": divergences_data,
                "performance_variance": performance_variance_data,
            }

        else:
            raise ValueError(f"Unknown component: {component}")

    def _hash_data(self, data: Any) -> str:
        """Generate deterministic hash of data."""
        if isinstance(data, dict):
            encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        else:
            encoded = str(data)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
