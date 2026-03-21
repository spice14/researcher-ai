"""Ingestion Service as MCP Tool — text extraction and chunking.

Wraps ingestion.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any, List
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.ingestion.service import IngestionService


class IngestionTool(MCPTool):
    """MCP wrapper for ingestion service."""

    def __init__(self, embedding_service=None, vector_store=None):
        """Initialize with internal service instance and optional embedding/vector store."""
        self._service = IngestionService()
        self._embedding_service = embedding_service
        self._vector_store = vector_store
    
    def manifest(self) -> MCPManifest:
        """Define ingestion tool interface."""
        return MCPManifest(
            name="ingestion",
            version="1.0.0",
            description="Extract and chunk raw text from research papers",
            input_schema={
                "type": "object",
                "properties": {
                    "raw_text": {
                        "type": "string",
                        "description": "Raw text to ingest"
                    },
                    "source_id": {
                        "type": "string",
                        "description": "Paper identifier"
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": "Max characters per chunk",
                        "minimum": 200,
                        "default": 1000
                    },
                    "chunk_overlap": {
                        "type": "integer",
                        "description": "Overlapping characters",
                        "minimum": 0,
                        "default": 100
                    }
                },
                "required": ["raw_text", "source_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "text": {"type": "string"},
                                "page": {"type": "integer"}
                            }
                        }
                    },
                    "telemetry": {"type": "object"},
                    "warnings": {"type": "array"}
                },
                "required": ["source_id", "chunks"]
            },
            deterministic=True
        )
    
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute ingestion with explicit payload.
        
        Args:
            payload: Must contain raw_text, source_id, optional chunk_size/overlap
        
        Returns:
            Result dict with chunks and telemetry
        """
        # Extract parameters
        raw_text = payload.get("raw_text")
        source_id = payload.get("source_id")
        chunk_size = payload.get("chunk_size", 1000)
        chunk_overlap = payload.get("chunk_overlap", 100)
        
        if not raw_text:
            raise ValueError("raw_text is required")
        if not source_id:
            raise ValueError("source_id is required")
        
        # Call service (unchanged logic)
        from services.ingestion.schemas import IngestionRequest
        
        request = IngestionRequest(
            source_id=source_id,
            raw_text=raw_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        result = self._service.ingest_text(request)
        
        # Persist embeddings to vector store if available (Phase 1)
        if self._embedding_service is not None and self._vector_store is not None:
            try:
                from services.embedding.schemas import EmbeddingRequest
                from services.vectorstore.schemas import VectorAddRequest

                texts = [c.text for c in result.chunks]
                emb_result = self._embedding_service.embed(EmbeddingRequest(texts=texts))
                add_req = VectorAddRequest(
                    collection="chunks",
                    ids=[c.chunk_id for c in result.chunks],
                    embeddings=emb_result.embeddings,
                    documents=texts,
                    metadatas=[
                        {
                            "source_id": c.source_id,
                            "start_char": str(c.start_char),
                            "end_char": str(c.end_char),
                        }
                        for c in result.chunks
                    ],
                )
                self._vector_store.add_embeddings(add_req)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Embedding persistence failed: %s", exc)

        # Return as explicit dict (schema matches output_schema)
        return {
            "source_id": result.source_id,
            "chunks": [
                {
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
                    "metric_names": chunk.metric_names
                }
                for chunk in result.chunks
            ],
            "telemetry": {
                "numeric_strings": result.telemetry.numeric_strings,
                "unit_strings": result.telemetry.unit_strings,
                "metric_names": result.telemetry.metric_names,
                "context_ids": result.telemetry.context_ids
            },
            "warnings": result.warnings,
            "metadata": result.metadata
        }
