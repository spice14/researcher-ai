"""Consolidation as MCP Tool — structured analysis summary."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.consolidation.service import ConsolidationService
from services.consolidation.schemas import ConsolidationRequest


class ConsolidationTool(MCPTool):
    """MCP wrapper for the consolidation service."""

    def __init__(self, service: ConsolidationService | None = None) -> None:
        self._service = service or ConsolidationService()

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="consolidation",
            version="1.0.0",
            description="Consolidate hypothesis, beliefs, clusters, and contradictions into analysis summary",
            input_schema={
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "object"},
                    "beliefs": {"type": "array"},
                    "clusters": {"type": "array"},
                    "contradictions": {"type": "array"},
                    "claims": {"type": "array"},
                    "session_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "key_findings": {"type": "array"},
                    "evidence_gaps": {"type": "array"},
                    "confidence_assessment": {"type": "string"},
                    "hypothesis_status": {"type": "string"},
                },
            },
            deterministic=True,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = ConsolidationRequest(
            hypothesis=payload.get("hypothesis") or payload.get("final_hypothesis"),
            beliefs=payload.get("beliefs", []),
            clusters=payload.get("clusters", []),
            contradictions=payload.get("contradictions", []),
            claims=payload.get("claims", []),
            session_id=payload.get("session_id"),
        )
        result = self._service.consolidate(request)
        return result.model_dump()
