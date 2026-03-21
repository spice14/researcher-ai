"""Vector Store as MCP Tool — persistent embedding storage and retrieval."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.vectorstore.service import VectorStoreService
from services.vectorstore.schemas import VectorAddRequest, VectorDeleteRequest, VectorQueryRequest


class VectorStoreTool(MCPTool):
    """MCP wrapper for the vector store service."""

    def __init__(self, service: VectorStoreService | None = None) -> None:
        self._service = service or VectorStoreService()

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="vector_store",
            version="1.0.0",
            description="Persistent vector embedding storage and semantic retrieval via Chroma",
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "query", "delete"],
                        "description": "Operation to perform",
                    },
                    "collection": {"type": "string", "description": "Collection name"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                    "embeddings": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                    "documents": {"type": "array", "items": {"type": "string"}},
                    "metadatas": {"type": "array", "items": {"type": "object"}},
                    "query_embedding": {"type": "array", "items": {"type": "number"}},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 100},
                    "where": {"type": "object"},
                },
                "required": ["operation"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "collection": {"type": "string"},
                    "backend": {"type": "string"},
                    "matches": {"type": "array"},
                    "query_count": {"type": "integer"},
                },
            },
            deterministic=False,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        operation = payload.get("operation")
        if not operation:
            raise ValueError("operation is required")

        collection = payload.get("collection", "scholaros_chunks")

        if operation == "add":
            request = VectorAddRequest(
                collection=collection,
                ids=payload["ids"],
                embeddings=payload["embeddings"],
                documents=payload.get("documents", []),
                metadatas=payload.get("metadatas", []),
            )
            return self._service.add_embeddings(request)

        elif operation == "query":
            request = VectorQueryRequest(
                collection=collection,
                query_embedding=payload["query_embedding"],
                top_k=payload.get("top_k", 10),
                where=payload.get("where"),
            )
            result = self._service.query(request)
            return {
                "matches": [m.model_dump() for m in result.matches],
                "collection": result.collection,
                "query_count": result.query_count,
            }

        elif operation == "delete":
            request = VectorDeleteRequest(
                collection=collection,
                ids=payload["ids"],
            )
            return self._service.delete(request)

        else:
            raise ValueError(f"Unknown operation: {operation}")
