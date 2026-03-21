"""ScholarOS CLI — main entry point for researchers.

Usage:
    python -m cli.app ingest <pdf>
    python -m cli.app analyze <paper_id_or_pdf>
    python -m cli.app analyze --pause-at hypothesis_critique_loop <pdf>
    python -m cli.app map --topic "attention mechanisms"
    python -m cli.app hypothesize <session_id>
    python -m cli.app propose <session_id>
    python -m cli.app status
    python -m cli.app trace <session_id>
    python -m cli.app resume
    python -m cli.app papers
    python -m cli.app claims <paper_id>
    python -m cli.app export <session_id> [--format latex]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def cmd_ingest(args) -> int:
    """Ingest a PDF and print chunk count."""
    from cli.runner import ingest_pdf, build_registry
    from cli.formatters import fmt_ingestion

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        registry, emb, vs = build_registry()
        result = ingest_pdf(args.pdf, source_id=args.source_id)
        print(fmt_ingestion(result))

        # Persist to metadata store if available
        try:
            from services.metadatastore.service import MetadataStoreService
            from services.metadatastore.schemas import PaperRecord
            from datetime import datetime, timezone

            store = MetadataStoreService()
            import os as _os
            paper = PaperRecord(
                paper_id=result["source_id"],
                title=_os.path.splitext(_os.path.basename(args.pdf))[0],
                pdf_path=args.pdf,
                chunk_count=len(result["chunks"]),
                ingestion_timestamp=datetime.now(timezone.utc),
            )
            store.save_paper(paper)
            print(f"\nPaper saved to metadata store: {result['source_id']}")
        except Exception as exc:
            print(f"  (metadata persistence skipped: {exc})")

        return 0
    except Exception as exc:
        print(f"Error during ingestion: {exc}", file=sys.stderr)
        return 1


def cmd_analyze(args) -> int:
    """Run the full pipeline on a PDF or paper ID."""
    from cli.runner import run_full_analysis
    from cli.formatters import fmt_trace

    target = args.target
    pause_at = getattr(args, "pause_at", None)

    # Check if it's a PDF path
    if os.path.exists(target) and target.endswith(".pdf"):
        pdf_path = target
        source_id = args.source_id
    else:
        print(f"Error: {target} is not a valid PDF path.", file=sys.stderr)
        return 1

    try:
        result = run_full_analysis(pdf_path, source_id=source_id, pause_at=pause_at)
        print(fmt_trace(result))

        if result.get("paused"):
            print(f"\nPipeline PAUSED before '{pause_at}'.")
            print("Run `python -m cli.app resume` to continue.")
            # Save orchestrator state to file
            _save_resume_state(result)
        else:
            print(f"\nAnalysis complete. Session: {result['session_id']}")

        return 0
    except Exception as exc:
        print(f"Error during analysis: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_map(args) -> int:
    """Build a literature cluster map."""
    from services.embedding.service import EmbeddingService
    from services.vectorstore.service import VectorStoreService
    from services.mapping.service import LiteratureMappingService
    from services.mapping.schemas import MappingRequest
    from cli.formatters import fmt_cluster_map

    emb = EmbeddingService()
    vs = VectorStoreService()
    svc = LiteratureMappingService(vector_store=vs, embedding_service=emb)

    request = MappingRequest(
        topic=getattr(args, "topic", None),
        seed_paper_id=getattr(args, "seed_paper_id", None),
        top_k=getattr(args, "top_k", 50),
        min_cluster_size=getattr(args, "min_cluster_size", 3),
    )

    result = svc.build_map(request)
    result_dict = result.model_dump()
    print(fmt_cluster_map(result_dict))
    return 0


def cmd_trace(args) -> int:
    """Print trace for a session."""
    from cli.inspector import ProvenanceInspector
    from core.mcp.trace import JSONTraceStore
    from cli.formatters import fmt_trace

    trace_dir = os.environ.get("TRACE_DIR", "outputs/traces")
    store = JSONTraceStore(base_dir=trace_dir)
    inspector = ProvenanceInspector(trace_store=store)
    entries = inspector.trace_session(args.session_id)

    if not entries:
        # Try loading from file directly
        fpath = os.path.join(trace_dir, f"{args.session_id}.json")
        if os.path.exists(fpath):
            with open(fpath) as f:
                data = json.load(f)
            print(fmt_trace(data))
        else:
            print(f"No trace found for session: {args.session_id}")
        return 0

    trace_data = {"session_id": args.session_id, "entries": entries}
    print(fmt_trace(trace_data))
    return 0


def cmd_papers(args) -> int:
    """List all ingested papers."""
    from services.metadatastore.service import MetadataStoreService
    from cli.formatters import fmt_papers

    try:
        store = MetadataStoreService()
        papers = store.list_papers()
        print(fmt_papers([p.model_dump() for p in papers]))
        return 0
    except Exception as exc:
        print(f"Error accessing metadata store: {exc}", file=sys.stderr)
        return 1


def cmd_claims(args) -> int:
    """List claims for a paper."""
    from services.metadatastore.service import MetadataStoreService
    from cli.formatters import fmt_claims

    try:
        store = MetadataStoreService()
        claims = store.get_claims(args.paper_id)
        print(fmt_claims([c.model_dump() for c in claims]))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_status(args) -> int:
    """Print system status (services available)."""
    from services.embedding.service import EmbeddingService
    from services.vectorstore.service import VectorStoreService

    emb = EmbeddingService()
    vs = VectorStoreService()

    print("\nScholarOS System Status")
    print("=" * 40)
    print(f"  Embedding backend:  {emb.backend} (dim={emb.dimension})")
    print(f"  Vector store:       {'chroma' if not vs.is_using_fallback else 'in-memory (Chroma unavailable)'}")
    print(f"  Metadata store:     SQLite")

    # Check Ollama
    try:
        from core.llm.client import OllamaClient
        client = OllamaClient()
        available = client.is_available()
        print(f"  LLM (Ollama):       {'available' if available else 'unavailable'}")
    except Exception:
        print(f"  LLM (Ollama):       unavailable")

    trace_dir = os.environ.get("TRACE_DIR", "outputs/traces")
    trace_count = len([f for f in os.listdir(trace_dir) if f.endswith(".json")]) if os.path.isdir(trace_dir) else 0
    print(f"  Sessions traced:    {trace_count}")
    return 0


def cmd_export(args) -> int:
    """Export a session's proposal as Markdown or LaTeX."""
    trace_dir = os.environ.get("TRACE_DIR", "outputs/traces")
    fpath = os.path.join(trace_dir, f"{args.session_id}.json")

    if not os.path.exists(fpath):
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1

    with open(fpath) as f:
        trace = json.load(f)

    final = trace.get("final_output", {})
    proposal = final.get("proposal") or final

    export_fmt = getattr(args, "format", "md")
    if export_fmt == "latex":
        latex = proposal.get("latex_output")
        if not latex:
            # Generate on-the-fly
            from services.proposal.latex_renderer import render_proposal
            sections = proposal.get("sections", [])
            refs = proposal.get("references", [])
            tables = proposal.get("evidence_tables", [])
            latex = render_proposal(
                title=proposal.get("hypothesis_id", "Research Proposal"),
                sections=sections,
                references=refs,
                evidence_tables=tables,
            )
        out_path = f"{args.session_id}_proposal.tex"
        with open(out_path, "w") as f:
            f.write(latex)
        print(f"LaTeX proposal written to: {out_path}")
    else:
        md = proposal.get("full_markdown", str(final))
        out_path = f"{args.session_id}_proposal.md"
        with open(out_path, "w") as f:
            f.write(md)
        print(f"Markdown proposal written to: {out_path}")

    return 0


def cmd_resume(args) -> int:
    """Resume a paused pipeline."""
    state_path = ".resume_state.json"
    if not os.path.exists(state_path):
        print("No paused pipeline found. Run 'analyze --pause-at <tool>' first.")
        return 1

    print("Resuming paused pipeline...")
    # The orchestrator state is in-memory; for full persistence this would reload
    # For now: inform the user that resume requires the same process
    print("Note: Pipeline resume requires the same Python process.")
    print("Use `python -m cli.app analyze` to start a new analysis.")
    return 0


def _save_resume_state(result: dict) -> None:
    """Save minimal resume state to disk."""
    import json
    state = {
        "session_id": result.get("session_id"),
        "paused": result.get("paused", False),
    }
    with open(".resume_state.json", "w") as f:
        json.dump(state, f, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli.app",
        description="ScholarOS — Agentic Research Assistant CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest a PDF file")
    p_ingest.add_argument("pdf", help="Path to the PDF file")
    p_ingest.add_argument("--source-id", dest="source_id", help="Override paper ID")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run full pipeline on a PDF")
    p_analyze.add_argument("target", help="PDF path or paper ID")
    p_analyze.add_argument("--source-id", dest="source_id", help="Override paper ID")
    p_analyze.add_argument("--pause-at", dest="pause_at", help="Tool name to pause before")

    # map
    p_map = sub.add_parser("map", help="Build literature cluster map")
    p_map.add_argument("--topic", help="Topic query")
    p_map.add_argument("--seed-paper-id", dest="seed_paper_id", help="Seed paper ID")
    p_map.add_argument("--top-k", dest="top_k", type=int, default=50)
    p_map.add_argument("--min-cluster-size", dest="min_cluster_size", type=int, default=3)

    # trace
    p_trace = sub.add_parser("trace", help="Print provenance trace for a session")
    p_trace.add_argument("session_id", help="Session ID")

    # papers
    sub.add_parser("papers", help="List all ingested papers")

    # claims
    p_claims = sub.add_parser("claims", help="List claims for a paper")
    p_claims.add_argument("paper_id", help="Paper ID")

    # status
    sub.add_parser("status", help="Print system status")

    # resume
    sub.add_parser("resume", help="Resume a paused pipeline")

    # export
    p_export = sub.add_parser("export", help="Export proposal as Markdown or LaTeX")
    p_export.add_argument("session_id", help="Session ID")
    p_export.add_argument("--format", default="md", choices=["md", "latex"])

    return parser


_COMMANDS = {
    "ingest": cmd_ingest,
    "analyze": cmd_analyze,
    "map": cmd_map,
    "trace": cmd_trace,
    "papers": cmd_papers,
    "claims": cmd_claims,
    "status": cmd_status,
    "resume": cmd_resume,
    "export": cmd_export,
}


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
