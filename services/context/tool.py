"""Context Extraction Service as MCP Tool — experimental context discovery.

Wraps context.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.context.service import ContextExtractor


class ContextTool(MCPTool):
    """MCP wrapper for context extraction service."""

    def __init__(self):
        """Initialize with internal service instance."""
        self._service = ContextExtractor()

    def manifest(self) -> MCPManifest:
        """Define context extraction tool interface."""
        return MCPManifest(
            name="context",
            version="1.0.0",
            description="Extract experimental context identity from ingested text chunks",
            input_schema={
                "type": "object",
                "properties": {
                    "chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "source_id": {"type": "string"},
                                "text": {"type": "string"},
                                "page": {"type": "integer"},
                                "context_id": {"type": "string"}
                            },
                            "required": ["chunk_id", "source_id", "text"]
                        },
                        "description": "Ingestion chunks to analyze"
                    }
                },
                "required": ["chunks"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "contexts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "context_id": {"type": "string"},
                                "dataset": {"type": "string"},
                                "task": {"type": "string"},
                                "metric": {"type": "string"}
                            }
                        }
                    },
                    "chunks": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Updated chunks with assigned context_ids"
                    },
                    "contexts_created": {"type": "integer"},
                    "unknown_chunks": {"type": "integer"},
                    "warnings": {"type": "array"}
                },
                "required": ["contexts", "chunks", "contexts_created", "unknown_chunks"]
            },
            deterministic=True
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute context extraction with explicit payload."""
        from services.ingestion.schemas import IngestionChunk

        chunk_dicts = payload.get("chunks", [])
        if not chunk_dicts:
            return {
                "contexts": [],
                "chunks": [],
                "contexts_created": 0,
                "unknown_chunks": 0,
                "warnings": ["empty chunk list provided"],
            }

        # Reconstruct IngestionChunk objects
        chunks = []
        for c in chunk_dicts:
            chunks.append(
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

        result = self._service.extract_contexts(chunks)

        # Serialize contexts from registry
        contexts_out = []
        for ctx_id, ctx in result.registry.contexts.items():
            contexts_out.append({
                "context_id": ctx.context_id,
                "dataset": ctx.dataset,
                "task": ctx.task.value if hasattr(ctx.task, "value") else str(ctx.task),
                "metric": ctx.metric.name if hasattr(ctx.metric, "name") else str(ctx.metric),
                "metric_higher_is_better": ctx.metric.higher_is_better if hasattr(ctx.metric, "higher_is_better") else True,
            })

        # Serialize updated chunks
        chunks_out = []
        for chunk in result.chunks:
            chunks_out.append({
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "text": chunk.text,
                "page": chunk.page,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "text_hash": chunk.text_hash,
                "context_id": chunk.context_id,
                "numeric_strings": chunk.numeric_strings,
                "unit_strings": chunk.unit_strings,
                "metric_names": chunk.metric_names,
            })

        return {
            "contexts": contexts_out,
            "chunks": chunks_out,
            "contexts_created": result.contexts_created,
            "unknown_chunks": result.unknown_chunks,
            "warnings": [],
        }
