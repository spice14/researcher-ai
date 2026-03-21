"""Pipeline setup for ScholarOS CLI.

Initializes registry, tool registration, orchestrator, and session management.
Supports graceful degradation without Docker (lexical RAG fallback).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_registry():
    """Build and populate the MCP tool registry with all available tools."""
    from core.mcp.registry import MCPRegistry
    from services.embedding.service import EmbeddingService
    from services.vectorstore.service import VectorStoreService
    from services.metadatastore.service import MetadataStoreService

    from services.ingestion.tool import IngestionTool
    from services.context.tool import ContextTool
    from services.extraction.tool import ExtractionTool
    from services.normalization.tool import NormalizationTool
    from services.contradiction.tool import ContradictionTool
    from services.belief.tool import BeliefTool
    from services.rag.tool import RAGTool
    from services.multimodal.tool import MultimodalTool
    from services.proposal.tool import ProposalTool
    from services.agent_loop.tool import AgentLoopTool
    from services.consolidation.tool import ConsolidationTool
    from services.mapping.tool import MappingTool

    # Initialize shared services
    emb = EmbeddingService()
    vs = VectorStoreService()

    if emb.backend == "hash_fallback":
        logger.warning("Using hash-based embeddings (no sentence-transformers installed)")
    if vs.is_using_fallback:
        logger.warning("Using in-memory vector store (Chroma unavailable — lexical RAG fallback active)")

    registry = MCPRegistry()
    registry.register(IngestionTool(embedding_service=emb, vector_store=vs))
    registry.register(ContextTool())
    registry.register(ExtractionTool())
    registry.register(NormalizationTool())
    registry.register(ContradictionTool())
    registry.register(BeliefTool())
    registry.register(RAGTool(vector_store=vs, embedding_service=emb))
    registry.register(MultimodalTool())
    registry.register(ProposalTool())
    registry.register(AgentLoopTool())
    registry.register(ConsolidationTool())
    from services.mapping.service import LiteratureMappingService
    mapping_svc = LiteratureMappingService(vector_store=vs, embedding_service=emb)
    registry.register(MappingTool(service=mapping_svc))

    return registry, emb, vs


def build_orchestrator(registry=None):
    """Build the MCP orchestrator with trace store."""
    from services.orchestrator.mcp_orchestrator import MCPOrchestrator
    from core.mcp.trace import JSONTraceStore

    if registry is None:
        registry, _, _ = build_registry()

    import os
    trace_dir = os.environ.get("TRACE_DIR", "outputs/traces")
    os.makedirs(trace_dir, exist_ok=True)
    trace_store = JSONTraceStore(base_dir=trace_dir)

    return MCPOrchestrator(registry=registry, trace_store=trace_store)


def ingest_pdf(pdf_path: str, source_id: Optional[str] = None) -> dict:
    """Ingest a PDF file and return the ingestion result.

    Args:
        pdf_path: Path to the PDF file
        source_id: Optional paper ID (auto-generated from filename if not given)

    Returns:
        Ingestion result dict with chunks, telemetry, etc.
    """
    from services.ingestion.pdf_service import PDFIngestionService

    import os
    if source_id is None:
        base = os.path.basename(pdf_path)
        source_id = os.path.splitext(base)[0].replace(" ", "_")

    svc = PDFIngestionService()
    result = svc.ingest_pdf(pdf_path, source_id=source_id)

    # Return as dict-compatible format
    return {
        "source_id": result.source_id,
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "source_id": c.source_id,
                "text": c.text,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "context_id": c.context_id,
                "metric_names": c.metric_names,
            }
            for c in result.chunks
        ],
        "telemetry": {
            "metric_names": result.telemetry.metric_names,
            "context_ids": result.telemetry.context_ids,
        },
        "warnings": result.warnings,
    }


def run_full_analysis(pdf_path: str, source_id: Optional[str] = None, pause_at: Optional[str] = None) -> dict:
    """Run the full 7-step pipeline on a PDF.

    Args:
        pdf_path: Path to the PDF file
        source_id: Optional paper ID
        pause_at: Optional tool name to pause pipeline before

    Returns:
        ExecutionTrace as dict
    """
    from services.orchestrator.workflows import build_full_analysis_dag

    registry, _, _ = build_registry()
    orchestrator = build_orchestrator(registry=registry)

    ingestion_payload = ingest_pdf(pdf_path, source_id)
    dag = build_full_analysis_dag()

    trace = orchestrator.execute_dag(
        dag,
        initial_payload=ingestion_payload,
        user_input=f"analyze:{pdf_path}",
        pause_at=pause_at,
    )

    return {
        "session_id": trace.session_id,
        "started_at": trace.started_at.isoformat(),
        "completed_at": trace.completed_at.isoformat(),
        "final_output": trace.final_output,
        "entries": [
            {
                "sequence": e.sequence,
                "tool": e.tool,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "phase": e.phase,
            }
            for e in trace.entries
        ],
        "paused": orchestrator._paused_state is not None,
        "_orchestrator": orchestrator,
    }
