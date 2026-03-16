"""RAG Service as MCP Tool — semantic retrieval over indexed chunks.

Wraps rag.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.rag.service import RAGService


class RAGTool(MCPTool):
    """MCP wrapper for RAG retrieval service."""

    def __init__(self):
        """Initialize with internal service instance."""
        self._service = RAGService()

    def manifest(self) -> MCPManifest:
        """Define RAG tool interface."""
        return MCPManifest(
            name="rag",
            version="1.0.0",
            description="Deterministic retrieval over indexed text chunks via lexical overlap",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "corpus": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "source_id": {"type": "string"},
                                "text": {"type": "string"},
                                "start_char": {"type": "integer"},
                                "end_char": {"type": "integer"}
                            },
                            "required": ["chunk_id", "source_id", "text"]
                        },
                        "description": "Corpus of chunks to search"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of matches to return",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 5
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional source filter"
                    }
                },
                "required": ["query", "corpus"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "retrieval_method": {"type": "string"},
                    "matches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "source_id": {"type": "string"},
                                "score": {"type": "number"},
                                "text": {"type": "string"}
                            }
                        }
                    },
                    "warnings": {"type": "array"}
                },
                "required": ["query", "retrieval_method", "matches"]
            },
            deterministic=True
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute retrieval with explicit payload."""
        from services.ingestion.schemas import IngestionChunk
        from services.rag.schemas import QueryRequest

        query = payload.get("query")
        corpus_dicts = payload.get("corpus", [])
        top_k = payload.get("top_k", 5)
        source_ids = payload.get("source_ids")

        if not query:
            raise ValueError("query is required")

        # Reconstruct IngestionChunk objects from dicts
        corpus = []
        for c in corpus_dicts:
            corpus.append(
                IngestionChunk(
                    chunk_id=c.get("chunk_id"),
                    source_id=c.get("source_id"),
                    text=c.get("text"),
                    start_char=c.get("start_char", 0),
                    end_char=c.get("end_char", len(c.get("text", ""))),
                    text_hash=c.get("text_hash", ""),
                    context_id=c.get("context_id", "ctx_unknown"),
                    page=c.get("page", 1),
                    numeric_strings=c.get("numeric_strings", []),
                    unit_strings=c.get("unit_strings", []),
                    metric_names=c.get("metric_names", []),
                )
            )

        request = QueryRequest(
            query=query,
            corpus=corpus,
            top_k=top_k,
            source_ids=source_ids,
        )

        result = self._service.retrieve(request)

        return {
            "query": result.query,
            "retrieval_method": result.retrieval_method,
            "matches": [
                {
                    "chunk_id": m.chunk_id,
                    "source_id": m.source_id,
                    "score": m.score,
                    "text": m.text,
                    "start_char": m.start_char,
                    "end_char": m.end_char,
                }
                for m in result.matches
            ],
            "warnings": result.warnings,
        }
