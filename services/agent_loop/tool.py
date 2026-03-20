"""Agent Loop as MCP Tool — hypothesis-critique iteration."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest


class AgentLoopTool(MCPTool):
    """MCP wrapper for the hypothesis-critique loop."""

    def __init__(self, loop=None) -> None:
        self._loop = loop

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="agent_loop",
            version="1.0.0",
            description="Run bounded hypothesis-critique adversarial loop with convergence detection",
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {"type": "array", "description": "Structured claims"},
                    "contradictions": {"type": "array", "description": "Contradictions"},
                    "consensus_groups": {"type": "array", "description": "Consensus groups"},
                    "constraints": {"type": "string"},
                    "counter_evidence_chunks": {"type": "array"},
                    "max_iterations": {"type": "integer", "minimum": 1},
                    "confidence_threshold": {"type": "number"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "final_hypothesis": {"type": "object"},
                    "critiques": {"type": "array"},
                    "iterations_completed": {"type": "integer"},
                    "stopped_reason": {"type": "string"},
                    "converged": {"type": "boolean"},
                    "confidence_rationale": {"type": "string"},
                },
            },
            deterministic=False,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._loop is None:
            from agents.loop import HypothesisCritiqueLoop, LoopConfig
            from agents.hypothesis.agent import HypothesisInput

            config = LoopConfig(
                max_iterations=payload.get("max_iterations", 5),
                confidence_threshold=payload.get("confidence_threshold", 0.8),
            )
            loop = HypothesisCritiqueLoop(config=config)
        else:
            loop = self._loop
            from agents.hypothesis.agent import HypothesisInput

        inp = HypothesisInput(
            claims=payload.get("claims", []),
            contradictions=payload.get("contradictions", []),
            consensus_groups=payload.get("consensus_groups", []),
            constraints=payload.get("constraints", ""),
        )

        result = loop.run(
            inp,
            counter_evidence_chunks=payload.get("counter_evidence_chunks", []),
            contradiction_context=payload.get("contradictions", []),
        )

        hyp_dict = None
        confidence_rationale = None
        if result.final_hypothesis:
            hyp_dict = result.final_hypothesis.model_dump()
            confidence_rationale = getattr(result.final_hypothesis, 'rationale', None)

        converged = result.stopped_reason == "confidence_threshold_met"

        return {
            "final_hypothesis": hyp_dict,
            "critiques": [c.model_dump() for c in result.critiques],
            "iterations_completed": result.iterations_completed,
            "stopped_reason": result.stopped_reason,
            "converged": converged,
            "confidence_rationale": confidence_rationale,
            "trace_entries": result.trace_entries,
            "total_duration_ms": result.total_duration_ms,
        }
