"""Literature Mapping as MCP Tool — builds semantic literature maps."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.mapping.service import LiteratureMappingService
from services.mapping.schemas import MappingRequest


class MappingTool(MCPTool):
    """MCP wrapper for the literature mapping service."""

    def __init__(self, service: LiteratureMappingService | None = None) -> None:
        self._service = service or LiteratureMappingService()

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="mapping",
            version="1.0.0",
            description="Build semantic literature maps using HDBSCAN clustering and LLM labeling",
            input_schema={
                "type": "object",
                "properties": {
                    "seed_paper_id": {"type": "string", "description": "Seed paper ID"},
                    "topic": {"type": "string", "description": "Topic or abstract"},
                    "collection": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 5, "maximum": 200},
                    "min_cluster_size": {"type": "integer", "minimum": 2},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "map_id": {"type": "string"},
                    "clusters": {"type": "array"},
                    "noise_paper_ids": {"type": "array"},
                    "paper_count": {"type": "integer"},
                    "warnings": {"type": "array"},
                },
            },
            deterministic=False,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = MappingRequest(
            seed_paper_id=payload.get("seed_paper_id"),
            topic=payload.get("topic"),
            collection=payload.get("collection", "scholaros_chunks"),
            top_k=payload.get("top_k", 50),
            min_cluster_size=payload.get("min_cluster_size", 3),
        )
        result = self._service.build_map(request)
        return result.model_dump()
