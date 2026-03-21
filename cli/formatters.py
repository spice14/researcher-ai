"""Terminal output formatters for ScholarOS CLI.

Formats ClusterMap, ContradictionReport, Hypothesis, Proposal
and session/trace data for terminal display.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _hr(char: str = "─", width: int = 70) -> str:
    return char * width


def fmt_header(title: str) -> str:
    return f"\n{_hr('═')}\n  {title}\n{_hr('═')}\n"


def fmt_section(heading: str, body: str) -> str:
    return f"\n{_hr()}\n{heading}\n{_hr()}\n{body}\n"


def fmt_cluster_map(result: Dict) -> str:
    """Format a MappingResult dict for terminal output."""
    lines = [fmt_header("Literature Cluster Map")]
    clusters = result.get("clusters", [])
    paper_count = result.get("paper_count", 0)
    noise = result.get("noise_paper_ids", [])
    warnings = result.get("warnings", [])

    lines.append(f"Papers processed: {paper_count}")
    lines.append(f"Clusters found:   {len(clusters)}")
    lines.append(f"Noise papers:     {len(noise)}")

    if warnings:
        lines.append("\nWarnings:")
        for w in warnings:
            lines.append(f"  ! {w}")

    for i, cluster in enumerate(clusters, 1):
        label = cluster.get("label", "Unlabeled")
        count = cluster.get("paper_count", len(cluster.get("paper_ids", [])))
        reps = cluster.get("representative_paper_ids", [])
        lines.append(f"\n  [{i}] {label}  ({count} papers)")
        if reps:
            lines.append(f"      Representatives: {', '.join(reps[:3])}")

    return "\n".join(lines)


def fmt_hypothesis(hyp: Dict) -> str:
    """Format a Hypothesis dict for terminal output."""
    if not hyp:
        return "No hypothesis generated."

    lines = [fmt_header("Hypothesis")]
    lines.append(f"Statement:  {hyp.get('statement', '')}")
    confidence = hyp.get("confidence_score", hyp.get("qualitative_confidence", "?"))
    lines.append(f"Confidence: {confidence}")

    if hyp.get("rationale"):
        lines.append(f"\nRationale:\n  {hyp['rationale']}")

    assumptions = hyp.get("assumptions", [])
    if assumptions:
        lines.append("\nAssumptions:")
        for a in assumptions[:5]:
            lines.append(f"  - {a}")

    risks = hyp.get("known_risks", [])
    if risks:
        lines.append("\nKnown risks:")
        for r in risks[:3]:
            lines.append(f"  ! {r}")

    return "\n".join(lines)


def fmt_proposal(result: Dict) -> str:
    """Format a ProposalResult dict for terminal output."""
    lines = [fmt_header("Research Proposal")]
    lines.append(f"Proposal ID: {result.get('proposal_id', '')}")

    sections = result.get("sections", [])
    for sec in sections:
        heading = sec.get("heading", "")
        content = sec.get("content", "")
        lines.append(f"\n{'─'*60}\n{heading}\n{'─'*60}")
        lines.append(content[:500] + ("..." if len(content) > 500 else ""))

    refs = result.get("references", [])
    if refs:
        lines.append(f"\n[{len(refs)} references]")

    tables = result.get("evidence_tables", [])
    if tables:
        lines.append(f"[{len(tables)} evidence tables embedded]")

    warnings = result.get("warnings", [])
    if warnings:
        lines.append("\nWarnings:")
        for w in warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


def fmt_trace(trace_data: Dict) -> str:
    """Format an ExecutionTrace dict for terminal display."""
    lines = [fmt_header("Pipeline Trace")]
    lines.append(f"Session:    {trace_data.get('session_id', '')}")
    started = trace_data.get("started_at", "")
    completed = trace_data.get("completed_at", "")
    lines.append(f"Started:    {started}")
    lines.append(f"Completed:  {completed}")

    entries = trace_data.get("entries", [])
    lines.append(f"\nSteps ({len(entries)}):")
    for entry in entries:
        status = entry.get("status", "?")
        tool = entry.get("tool", "")
        dur = entry.get("duration_ms", 0)
        mark = "✓" if status == "success" else "✗"
        lines.append(f"  {mark} [{entry.get('sequence', 0)}] {tool:<30} {dur:6.1f}ms")
        if entry.get("error_message"):
            lines.append(f"      ERROR: {entry['error_message']}")

    return "\n".join(lines)


def fmt_papers(papers: List[Dict]) -> str:
    """Format a list of paper records for display."""
    if not papers:
        return "No papers ingested yet."

    lines = [fmt_header(f"Papers ({len(papers)})")]
    for p in papers:
        pid = p.get("paper_id", "")
        title = p.get("title", "Untitled")[:60]
        chunks = p.get("chunk_count", "?")
        lines.append(f"  {pid}")
        lines.append(f"    Title:  {title}")
        lines.append(f"    Chunks: {chunks}")
    return "\n".join(lines)


def fmt_claims(claims: List[Dict]) -> str:
    """Format a list of claims for display."""
    if not claims:
        return "No claims found."

    lines = [fmt_header(f"Claims ({len(claims)})")]
    for c in claims[:20]:
        cid = c.get("claim_id", "")
        text = c.get("text", "")[:100]
        conf = c.get("confidence_level", "?")
        lines.append(f"  [{conf}] {cid}: {text}")

    if len(claims) > 20:
        lines.append(f"  ... and {len(claims) - 20} more")
    return "\n".join(lines)


def fmt_ingestion(result: Dict) -> str:
    """Format ingestion result for display."""
    source_id = result.get("source_id", "")
    chunks = result.get("chunks", [])
    warnings = result.get("warnings", [])
    tel = result.get("telemetry", {})

    lines = [fmt_header("Ingestion Complete")]
    lines.append(f"Source ID:   {source_id}")
    lines.append(f"Chunks:      {len(chunks)}")
    if tel:
        lines.append(f"Metrics:     {len(tel.get('metric_names', []))} detected")
        lines.append(f"Context IDs: {', '.join(tel.get('context_ids', [])[:5])}")
    if warnings:
        for w in warnings:
            lines.append(f"  ! {w}")
    return "\n".join(lines)
