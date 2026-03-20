"""Embedding as MCP Tool — text-to-vector conversion."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.embedding.service import EmbeddingService
from services.embedding.schemas import EmbeddingRequest


class EmbeddingTool(MCPTool):
    """MCP wrapper for the embedding service."""

    def __init__(self, service: EmbeddingService | None = None) -> None:
        self._service = service or EmbeddingService()

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="embedding",
            version="1.0.0",
            description="Generate dense vector embeddings from text using sentence-transformers or Ollama",
            input_schema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Texts to embed",
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model override",
                    },
                },
                "required": ["texts"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "embeddings": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                    },
                    "model": {"type": "string"},
                    "dimension": {"type": "integer"},
                },
                "required": ["embeddings", "model", "dimension"],
            },
            deterministic=True,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        texts = payload.get("texts")
        if not texts:
            raise ValueError("texts is required")

        request = EmbeddingRequest(texts=texts, model=payload.get("model"))
        result = self._service.embed(request)

        return {
            "embeddings": result.embeddings,
            "model": result.model,
            "dimension": result.dimension,
        }
