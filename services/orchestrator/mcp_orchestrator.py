"""MCP Orchestrator — deterministic pipeline execution.

Executes tools in sequence, passing output to next input.
No reasoning, no branching, no LLM calls.
Only deterministic tool invocation.

Logs complete trace for reproducibility verification.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import time
import uuid
from dataclasses import dataclass
from warnings import warn

from core.mcp.registry import MCPRegistry, ToolNotFoundError
from core.mcp.trace import ExecutionTrace, TraceEntry, hash_payload, JSONTraceStore
from core.schemas.session import Session


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry policy for transient failures."""

    max_retries: int = 3
    base_backoff_seconds: float = 0.05


class InMemorySessionStore:
    """Local session store for phase tracking during orchestration."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session


class MCPOrchestrator:
    """Deterministic pipeline orchestrator.
    
    Executes a pre-defined list of tools in sequence.
    No control flow, no branching, no implicit dependencies.
    All state is passed through payloads.
    """
    
    def __init__(
        self,
        registry: MCPRegistry,
        *,
        retry_policy: Optional[RetryPolicy] = None,
        trace_store: Optional[JSONTraceStore] = None,
        session_store: Optional[InMemorySessionStore] = None,
    ):
        """
        Initialize orchestrator with tool registry.
        
        Args:
            registry: MCPRegistry containing all available tools
        """
        self._registry = registry
        self._retry_policy = retry_policy or RetryPolicy()
        self._trace_store = trace_store or JSONTraceStore()
        self._session_store = session_store or InMemorySessionStore()
    
    def execute_pipeline(
        self,
        pipeline: List[str],
        initial_payload: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        user_input: str = "orchestrator_pipeline",
        phase_labels: Optional[Dict[str, str]] = None,
        persist_trace: bool = True,
    ) -> ExecutionTrace:
        """
        Execute pipeline: invoke tools in sequence.
        
        Args:
            pipeline: Ordered list of tool names
            initial_payload: Starting input dict
        
        Returns:
            ExecutionTrace with full provenance and final output
        
        Raises:
            ToolNotFoundError: If any tool not found
            RuntimeError: If any tool execution fails
            ValueError: If pipeline invalid
        """
        # Validate pipeline
        self._registry.validate_pipeline(pipeline)
        
        # Initialize execution
        session_id = session_id or str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc)
        trace_entries: List[TraceEntry] = []
        current_payload = initial_payload.copy()

        # Session lifecycle
        phase_labels = phase_labels or {}
        session = self._session_store.get(session_id)
        if session is None:
            session = Session(
                session_id=session_id,
                user_input=user_input,
                active_paper_ids=[],
                hypothesis_ids=[],
                phase=phase_labels.get(pipeline[0], pipeline[0]),
                created_at=started_at,
                updated_at=started_at,
            )
            self._session_store.save(session)
        
        # Execute each tool
        for sequence, tool_name in enumerate(pipeline):
            # Get tool
            try:
                tool = self._registry.get(tool_name)
            except ToolNotFoundError as e:
                raise RuntimeError(f"Execution failed at step {sequence}: {str(e)}")
            
            # Build phase and schema-pruned input
            phase = phase_labels.get(tool_name, tool_name)
            manifest = tool.manifest()
            step_payload = self._prune_payload_for_schema(current_payload, manifest.input_schema)

            # Execute with bounded retries
            result = {}
            status = "error"
            error_msg = None
            input_hash = hash_payload(step_payload)
            output_hash = hash_payload({})

            for attempt in range(1, self._retry_policy.max_retries + 1):
                step_start = time.time()
                try:
                    result = tool.call(step_payload)
                    status = "success"
                    error_msg = None
                except Exception as e:
                    status = "error"
                    error_msg = str(e)
                    result = {}

                step_duration = (time.time() - step_start) * 1000  # ms
                output_hash = hash_payload(result)

                trace_entries.append(TraceEntry(
                    sequence=sequence,
                    tool=tool_name,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    timestamp=datetime.now(timezone.utc),
                    status=status,
                    error_message=error_msg,
                    duration_ms=step_duration,
                    attempt=attempt,
                    phase=phase,
                    model_name=result.get("model_name") if isinstance(result, dict) else None,
                    prompt_version=result.get("prompt_version") if isinstance(result, dict) else None,
                    token_usage=result.get("token_usage") if isinstance(result, dict) else None,
                ))

                if status == "success":
                    break

                if attempt >= self._retry_policy.max_retries or not self._is_transient_error(error_msg or ""):
                    break

                # Deterministic bounded backoff.
                time.sleep(self._retry_policy.base_backoff_seconds * attempt)

            # Stop on terminal error
            if status == "error":
                failed_session = session.model_copy(update={
                    "phase": f"failed:{phase}",
                    "updated_at": datetime.now(timezone.utc),
                })
                self._session_store.save(failed_session)
                raise RuntimeError(
                    f"Tool '{tool_name}' failed at step {sequence}: {error_msg}"
                )

            # Update session phase after successful step
            session = session.model_copy(update={
                "phase": phase,
                "updated_at": datetime.now(timezone.utc),
            })
            self._session_store.save(session)
            
            # Pass result to next tool
            current_payload = result
        
        # Create final trace
        completed_at = datetime.now(timezone.utc)
        final_output_hash = hash_payload(current_payload)
        
        trace = ExecutionTrace(
            session_id=session_id,
            started_at=started_at,
            completed_at=completed_at,
            entries=trace_entries,
            final_output_hash=final_output_hash,
            final_output=current_payload,
            pipeline_definition=pipeline
        )

        if persist_trace:
            try:
                self._trace_store.save(trace)
            except Exception as exc:
                warn(f"Trace persistence failed for session {session_id}: {exc}")
        
        return trace

    @staticmethod
    def _is_transient_error(message: str) -> bool:
        m = message.lower()
        transient_signals = ["timeout", "timed out", "429", "rate limit", "temporary", "connection reset"]
        return any(sig in m for sig in transient_signals)

    @staticmethod
    def _prune_payload_for_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Prune payload to schema properties and validate required keys.

        Uses lightweight JSON-schema subset enforcement to avoid adding dependencies.
        """
        if schema.get("type") != "object":
            return payload

        properties = schema.get("properties", {}) or {}
        required = schema.get("required", []) or []
        pruned = {k: payload[k] for k in properties.keys() if k in payload}

        missing = [k for k in required if k not in pruned]
        if missing:
            raise ValueError(f"Input schema validation failed: missing required fields {missing}")

        return pruned
    
    def validate_pipeline(self, pipeline: List[str]) -> bool:
        """
        Check if pipeline can execute (all tools exist).
        
        Args:
            pipeline: List of tool names
        
        Returns:
            True if valid, False otherwise
        """
        try:
            self._registry.validate_pipeline(pipeline)
            return True
        except (ValueError, ToolNotFoundError):
            return False
