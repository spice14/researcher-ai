"""
E2E Test Harness — ScholarOS Phase 0–4
Pipeline: ingestion → extraction → normalization → belief → contradiction
Generates detailed per-paper JSON and Markdown reports.
"""

import os
import sys
import glob
import json
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Ensure workspace root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mcp.registry import MCPRegistry
from services.ingestion.tool import IngestionTool
from services.extraction.tool import ExtractionTool
from services.normalization.tool import NormalizationTool
from services.contradiction.tool import ContradictionTool
from services.belief.tool import BeliefTool

INTEGRITY_PAPERS_DIR = "outputs/integrity_papers"
CACHE_PAPERS_DIR = "outputs/ingestion_cache_v3_full62_uncached"
REPORT_JSON = "reports/e2e_full_report.json"
REPORT_MD = "reports/e2e_full_report.md"
BATCH_SIZE = 25

# ── Paper selection ─────────────────────────────────────────────────────────

def select_papers() -> List[Tuple[str, str, str]]:
    """Return list of (paper_id, source_type, path) tuples."""
    results: List[Tuple[str, str, str]] = []

    # Full-artifact papers (integrity_papers/)
    for name in sorted(os.listdir(INTEGRITY_PAPERS_DIR)):
        full_path = os.path.join(INTEGRITY_PAPERS_DIR, name)
        if os.path.isdir(full_path):
            results.append((name, "integrity", full_path))

    # Cached JSON papers
    cached = sorted(glob.glob(os.path.join(CACHE_PAPERS_DIR, "*.json")))
    for path in cached:
        name = os.path.splitext(os.path.basename(path))[0]
        results.append((name, "cached_json", path))

    return results[:BATCH_SIZE]


# ── Text extraction from paper sources ──────────────────────────────────────

def _text_from_sections(sections: List[Dict]) -> str:
    parts = []
    for sec in sections:
        title = sec.get("title", "")
        content = sec.get("content", "")
        if title:
            parts.append(f"\n## {title}\n")
        if content:
            parts.append(content)
    return "\n".join(parts).strip()


def _preflight_cached_artifact(paper_id: str, data: Dict[str, Any], selected_source: str, raw_text: str) -> Dict[str, Any]:
    """Run deterministic preflight checks for cached artifacts.

    This catches suspicious payloads before ingestion (e.g., empty section content,
    proceedings stubs, or unexpectedly tiny text payloads).
    """
    title = (data.get("title") or "").strip()
    abstract = (data.get("abstract") or "").strip()
    sections = data.get("sections") or []
    nonempty_sections = 0
    sections_chars = 0
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        content = (sec.get("content") or "").strip()
        if content:
            nonempty_sections += 1
            sections_chars += len(content)

    warnings: List[str] = []
    text_len = len(raw_text.strip())

    is_proceedings_title = "proceedings" in title.lower()

    if text_len == 0:
        warnings.append("EMPTY_TEXT_PAYLOAD: no usable text found in cached artifact")

    if selected_source in ("raw_text", "full_text", "text", "paper_text") and sections and nonempty_sections == 0:
        warnings.append(
            "SECTIONS_EMPTY_CONTENT: sections exist but all section.content values are empty; using top-level full text"
        )

    if selected_source == "fallback_abstract_sections" and text_len < 5000:
        warnings.append(
            "LOW_TEXT_VOLUME_FALLBACK: fallback text is very short; artifact may be partial"
        )

    if is_proceedings_title and text_len < 120000:
        warnings.append(
            "LIKELY_PROCEEDINGS_STUB: title indicates proceedings and text volume is modest"
        )

    if len(raw_text) > 50000 and nonempty_sections == 0:
        warnings.append(
            "RAWTEXT_SECTION_MISMATCH: large full text present while section content is empty"
        )

    return {
        "source_type": "cached_json",
        "selected_text_source": selected_source,
        "text_length": text_len,
        "title": title,
        "abstract_length": len(abstract),
        "sections_count": len(sections),
        "nonempty_sections": nonempty_sections,
        "sections_chars": sections_chars,
        "warnings": warnings,
        "paper_id": paper_id,
    }


def load_paper(paper_id: str, source_type: str, path: str) -> Tuple[str, str, Dict]:
    """Return (raw_text, source_id, meta) for a paper."""
    if source_type == "integrity":
        with open(os.path.join(path, "metadata.json")) as f:
            meta = json.load(f)
        md_path = os.path.join(path, "paper.md")
        with open(md_path) as f:
            raw_text = f.read()
        source_id = meta.get("id") or paper_id
        meta["preflight"] = {
            "source_type": "integrity",
            "selected_text_source": "paper_md",
            "text_length": len(raw_text.strip()),
            "warnings": [],
            "paper_id": paper_id,
        }
        return raw_text, source_id, meta

    # cached_json: prefer full-text fields from cache, then fallback to abstract+sections
    with open(path) as f:
        data = json.load(f)

    # Many cached artifacts store complete paper text in raw_text/full_text while
    # abstract and per-section content may be empty strings.
    selected_source = ""
    raw_text = (
        data.get("raw_text")
        or data.get("full_text")
        or data.get("text")
        or data.get("paper_text")
        or ""
    )

    if (data.get("raw_text") or "").strip():
        selected_source = "raw_text"
    elif (data.get("full_text") or "").strip():
        selected_source = "full_text"
    elif (data.get("text") or "").strip():
        selected_source = "text"
    elif (data.get("paper_text") or "").strip():
        selected_source = "paper_text"

    if not raw_text.strip():
        parts = []
        if data.get("abstract"):
            parts.append(data["abstract"])
        if data.get("sections"):
            parts.append(_text_from_sections(data["sections"]))
        raw_text = "\n\n".join(parts).strip()
        selected_source = "fallback_abstract_sections"

    source_id = data.get("id") or data.get("source_id") or paper_id
    meta = {k: v for k, v in data.items() if k not in ("sections",)}
    meta["preflight"] = _preflight_cached_artifact(paper_id, data, selected_source, raw_text)
    return raw_text, source_id, meta


# ── Registry (built once) ────────────────────────────────────────────────────

def build_registry() -> MCPRegistry:
    registry = MCPRegistry()
    registry.register(IngestionTool())
    registry.register(ExtractionTool())
    registry.register(NormalizationTool())
    registry.register(ContradictionTool())
    registry.register(BeliefTool())
    return registry


# ── Per-step execution ───────────────────────────────────────────────────────

def _run_step(registry: MCPRegistry, tool_name: str, payload: Dict) -> Tuple[Optional[Dict], float, Optional[str]]:
    """Run a single tool step. Returns (result, duration_ms, error_msg)."""
    t0 = time.perf_counter()
    try:
        result = registry.get(tool_name).call(payload)
        duration_ms = (time.perf_counter() - t0) * 1000
        return result, duration_ms, None
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        return None, duration_ms, f"{type(exc).__name__}: {exc}"


# ── Full pipeline ────────────────────────────────────────────────────────────

def run_pipeline(registry: MCPRegistry, paper_id: str, raw_text: str, source_id: str) -> Dict:
    """Run full pipeline. Returns detailed per-step metrics dict."""
    steps: Dict[str, Any] = {}
    pipeline_start = time.perf_counter()

    # ── Step 1: Ingestion ────────────────────────────────────────────────────
    ingestion_payload = {"raw_text": raw_text, "source_id": source_id}
    ingestion_result, ing_ms, ing_err = _run_step(registry, "ingestion", ingestion_payload)
    steps["ingestion"] = {
        "status": "error" if ing_err else "success",
        "duration_ms": round(ing_ms, 1),
        "error": ing_err,
        "chunks": len(ingestion_result.get("chunks", [])) if ingestion_result else 0,
        "warnings": ingestion_result.get("warnings", []) if ingestion_result else [],
    }
    if ing_err:
        return _build_result(steps, pipeline_start, "failed_at_ingestion", source_id)

    chunks = ingestion_result.get("chunks", [])

    # ── Step 2: Extraction ───────────────────────────────────────────────────
    extraction_payload = {"chunks": chunks, "source_id": source_id}
    extraction_result, ext_ms, ext_err = _run_step(registry, "extraction", extraction_payload)
    steps["extraction"] = {
        "status": "error" if ext_err else "success",
        "duration_ms": round(ext_ms, 1),
        "error": ext_err,
        "claims_extracted": len(extraction_result.get("claims", [])) if extraction_result else 0,
        "discarded_claims": extraction_result.get("discarded_claims", 0) if extraction_result else 0,
    }
    if ext_err:
        return _build_result(steps, pipeline_start, "failed_at_extraction", source_id)

    # No additional truncation needed – extraction service now guards obj length
    claims = extraction_result.get("claims", [])

    # ── Step 3: Normalization ────────────────────────────────────────────────
    normalization_payload = {"claims": claims}
    normalization_result, norm_ms, norm_err = _run_step(registry, "normalization", normalization_payload)
    steps["normalization"] = {
        "status": "error" if norm_err else "success",
        "duration_ms": round(norm_ms, 1),
        "error": norm_err,
        "normalized_claims": len(normalization_result.get("normalized_claims", [])) if normalization_result else 0,
        "failed_normalizations": len(normalization_result.get("failed_normalizations", [])) if normalization_result else 0,
    }
    if norm_err:
        return _build_result(steps, pipeline_start, "failed_at_normalization", source_id)

    normalized_claims = normalization_result.get("normalized_claims", [])

    # ── Step 4: Belief ───────────────────────────────────────────────────────
    belief_payload = {"normalized_claims": normalized_claims}
    belief_result, bel_ms, bel_err = _run_step(registry, "belief", belief_payload)
    belief_state = belief_result.get("belief_state") if belief_result else None
    steps["belief"] = {
        "status": "error" if bel_err else "success",
        "duration_ms": round(bel_ms, 1),
        "error": bel_err,
        "belief_state_present": bool(belief_state),
        "belief_metric": belief_state.get("metric") if belief_state else None,
        "consensus_strength": belief_state.get("consensus_strength") if belief_state else None,
        "qualitative_confidence": belief_state.get("qualitative_confidence") if belief_state else None,
    }
    if bel_err:
        return _build_result(steps, pipeline_start, "failed_at_belief", source_id)

    # ── Step 5: Contradiction ────────────────────────────────────────────────
    if not normalized_claims:
        steps["contradiction"] = {
            "status": "skipped",
            "duration_ms": 0,
            "error": None,
            "skip_reason": "No normalized_claims to analyze",
            "contradictions": 0,
            "consensus_groups": 0,
        }
        outcome = "partial_success"
    else:
        contradiction_payload = {
            "normalized_claims": normalized_claims,
            "belief_state": belief_state,
        }
        contradiction_result, cont_ms, cont_err = _run_step(registry, "contradiction", contradiction_payload)
        steps["contradiction"] = {
            "status": "error" if cont_err else "success",
            "duration_ms": round(cont_ms, 1),
            "error": cont_err,
            "contradictions": len(contradiction_result.get("contradictions", [])) if contradiction_result else 0,
            "consensus_groups": len(contradiction_result.get("consensus_groups", [])) if contradiction_result else 0,
        }
        outcome = "failed_at_contradiction" if cont_err else "success"

    return _build_result(steps, pipeline_start, outcome, source_id)


def _build_result(steps: Dict, pipeline_start: float, outcome: str, source_id: str) -> Dict:
    total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
    return {
        "source_id": source_id,
        "outcome": outcome,
        "total_duration_ms": total_ms,
        "steps": steps,
    }


# ── Summary statistics ───────────────────────────────────────────────────────

def compute_summary(results: List[Dict]) -> Dict:
    total = len(results)
    outcomes = [r["outcome"] for r in results]
    success = outcomes.count("success")
    partial = outcomes.count("partial_success")
    failed = total - success - partial

    total_chunks = sum(r["steps"].get("ingestion", {}).get("chunks", 0) for r in results)
    total_claims = sum(r["steps"].get("extraction", {}).get("claims_extracted", 0) for r in results)
    total_normalized = sum(r["steps"].get("normalization", {}).get("normalized_claims", 0) for r in results)
    total_contradictions = sum(r["steps"].get("contradiction", {}).get("contradictions", 0) for r in results)
    total_ms = sum(r["total_duration_ms"] for r in results)

    failure_reasons: Dict[str, int] = {}
    for r in results:
        if r["outcome"] not in ("success", "partial_success"):
            for step_name, step in r["steps"].items():
                if step.get("status") == "error" and step.get("error"):
                    key = f"{step_name}: {step['error'][:80]}"
                    failure_reasons[key] = failure_reasons.get(key, 0) + 1

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_papers": total,
        "success": success,
        "partial_success": partial,
        "failed": failed,
        "success_rate_pct": round(100 * success / total, 1),
        "partial_rate_pct": round(100 * partial / total, 1),
        "total_chunks": total_chunks,
        "total_claims_extracted": total_claims,
        "total_normalized_claims": total_normalized,
        "total_contradictions": total_contradictions,
        "total_pipeline_ms": round(total_ms, 1),
        "avg_pipeline_ms": round(total_ms / total, 1) if total else 0,
        "failure_reasons": failure_reasons,
    }


# ── Markdown report ──────────────────────────────────────────────────────────

def generate_markdown(summary: Dict, results: List[Dict], papers: List[Tuple[str, str, str]]) -> str:
    lines = []
    lines.append("# ScholarOS E2E Test Report — Phase 0–4")
    lines.append(f"\n**Run date:** {summary['run_at']}  ")
    lines.append(f"**Papers tested:** {summary['total_papers']}  ")
    lines.append(f"**Pipeline:** ingestion → extraction → normalization → belief → contradiction\n")

    lines.append("---\n")
    lines.append("## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total papers | {summary['total_papers']} |")
    lines.append(f"| ✅ Full success | {summary['success']} ({summary['success_rate_pct']}%) |")
    lines.append(f"| ⚠️ Partial success | {summary['partial_success']} ({summary['partial_rate_pct']}%) |")
    lines.append(f"| ❌ Failed | {summary['failed']} |")
    lines.append(f"| Total chunks ingested | {summary['total_chunks']} |")
    lines.append(f"| Total claims extracted | {summary['total_claims_extracted']} |")
    lines.append(f"| Total normalized claims | {summary['total_normalized_claims']} |")
    lines.append(f"| Total contradictions found | {summary['total_contradictions']} |")
    lines.append(f"| Total pipeline time | {summary['total_pipeline_ms']} ms |")
    lines.append(f"| Avg time per paper | {summary['avg_pipeline_ms']} ms |")

    if summary["failure_reasons"]:
        lines.append("\n### Failure Reasons\n")
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(summary["failure_reasons"].items(), key=lambda x: -x[1]):
            lines.append(f"| `{reason}` | {count} |")

    lines.append("\n---\n")
    lines.append("## Per-Paper Results\n")

    header = "| # | Paper ID | Type | Outcome | Chunks | Claims | Normalized | Contradictions | Total ms | Notes |"
    sep    = "|---|----------|------|---------|--------|--------|------------|---------------|----------|-------|"
    lines.append(header)
    lines.append(sep)

    paper_map = {pid: (ptype, ppath) for pid, ptype, ppath in papers}

    for i, r in enumerate(results, 1):
        paper_id = r["source_id"]
        ptype = paper_map.get(paper_id, ("", ""))[0]
        outcome = r["outcome"]
        outcome_icon = {"success": "✅", "partial_success": "⚠️"}.get(outcome, "❌")
        chunks = r["steps"].get("ingestion", {}).get("chunks", "-")
        claims = r["steps"].get("extraction", {}).get("claims_extracted", "-")
        normalized = r["steps"].get("normalization", {}).get("normalized_claims", "-")
        contradictions = r["steps"].get("contradiction", {}).get("contradictions", "-")
        total_ms = r["total_duration_ms"]
        # Build notes from first error encountered
        notes = ""
        for step_name, step in r["steps"].items():
            if step.get("status") in ("error", "skipped") and step.get("error"):
                notes = f"{step_name}: {step['error'][:60]}"
                break
        lines.append(f"| {i} | `{paper_id}` | {ptype} | {outcome_icon} {outcome} | {chunks} | {claims} | {normalized} | {contradictions} | {total_ms} | {notes} |")

    lines.append("\n---\n")
    lines.append("## Step-by-Step Timing (ms)\n")

    timing_header = "| Paper ID | Ingestion | Extraction | Normalization | Belief | Contradiction |"
    timing_sep    = "|----------|-----------|------------|---------------|--------|---------------|"
    lines.append(timing_header)
    lines.append(timing_sep)

    for r in results:
        pid = r["source_id"]
        ing = r["steps"].get("ingestion", {}).get("duration_ms", "-")
        ext = r["steps"].get("extraction", {}).get("duration_ms", "-")
        nor = r["steps"].get("normalization", {}).get("duration_ms", "-")
        bel = r["steps"].get("belief", {}).get("duration_ms", "-")
        con = r["steps"].get("contradiction", {}).get("duration_ms", "-")
        lines.append(f"| `{pid}` | {ing} | {ext} | {nor} | {bel} | {con} |")

    lines.append("\n---\n")
    lines.append("## Detailed Per-Paper Step Output\n")

    for r in results:
        pid = r["source_id"]
        outcome = r["outcome"]
        lines.append(f"### `{pid}`\n")
        lines.append(f"- **Outcome:** {outcome}")
        lines.append(f"- **Total time:** {r['total_duration_ms']} ms\n")
        for step_name, step in r["steps"].items():
            status_icon = {"success": "✅", "error": "❌", "skipped": "⏭️"}.get(step.get("status", ""), "?")
            lines.append(f"#### {status_icon} {step_name.capitalize()}")
            lines.append(f"- Status: `{step.get('status', 'unknown')}`")
            lines.append(f"- Duration: {step.get('duration_ms', '-')} ms")
            # Step-specific metrics
            for key in ("chunks", "claims_extracted", "discarded_claims", "normalized_claims",
                        "failed_normalizations", "belief_state_present", "belief_metric",
                        "consensus_strength", "qualitative_confidence", "contradictions", "consensus_groups"):
                if key in step:
                    lines.append(f"- {key.replace('_', ' ').title()}: `{step[key]}`")
            if step.get("error"):
                lines.append(f"- **Error:** `{step['error']}`")
            if step.get("warnings"):
                for w in step["warnings"][:3]:
                    lines.append(f"- ⚠️ Warning: {w}")
            lines.append("")

    lines.append("---\n")
    lines.append("*Generated by ScholarOS E2E Harness*")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("reports", exist_ok=True)
    registry = build_registry()

    papers = select_papers()
    print(f"Selected {len(papers)} papers for E2E testing.\n")

    results: List[Dict] = []
    paper_meta: List[Dict] = []

    for i, (paper_id, source_type, path) in enumerate(papers, 1):
        print(f"[{i:02d}/{len(papers)}] {paper_id} ({source_type})")
        try:
            raw_text, source_id, meta = load_paper(paper_id, source_type, path)
        except Exception as exc:
            print(f"  ✗ Load error: {exc}")
            results.append({
                "source_id": paper_id,
                "outcome": "load_error",
                "total_duration_ms": 0,
                "steps": {"load": {"status": "error", "duration_ms": 0, "error": str(exc)}},
            })
            paper_meta.append({"paper_id": paper_id, "source_type": source_type, "path": path})
            continue

        preflight = meta.get("preflight", {})
        preflight_warnings = preflight.get("warnings", []) if isinstance(preflight, dict) else []
        if preflight_warnings:
            print(f"  ⚠️ preflight warnings: {len(preflight_warnings)}")
            for w in preflight_warnings[:2]:
                print(f"     - {w}")

        result = run_pipeline(registry, paper_id, raw_text, source_id)
        outcome = result["outcome"]
        icon = {"success": "✅", "partial_success": "⚠️"}.get(outcome, "❌")
        steps = result["steps"]
        chunks = steps.get("ingestion", {}).get("chunks", 0)
        claims = steps.get("extraction", {}).get("claims_extracted", 0)
        norm = steps.get("normalization", {}).get("normalized_claims", 0)
        contradictions = steps.get("contradiction", {}).get("contradictions", 0)
        print(f"  {icon} {outcome} | chunks={chunks} claims={claims} normalized={norm} contradictions={contradictions} | {result['total_duration_ms']}ms")

        results.append(result)
        paper_meta.append({
            "paper_id": paper_id,
            "source_type": source_type,
            "path": path,
            "title": meta.get("title", ""),
            "preflight": meta.get("preflight", {}),
        })

    # Summary
    summary = compute_summary(results)
    print(f"\n{'='*60}")
    print(f"Results: {summary['success']}/{summary['total_papers']} full success, "
          f"{summary['partial_success']} partial, {summary['failed']} failed")
    print(f"Total pipeline time: {summary['total_pipeline_ms']} ms  "
          f"(avg {summary['avg_pipeline_ms']} ms/paper)")
    print(f"{'='*60}\n")

    # JSON report
    json_report = {
        "summary": summary,
        "papers": paper_meta,
        "results": results,
    }
    with open(REPORT_JSON, "w") as f:
        json.dump(json_report, f, indent=2, default=str)
    print(f"JSON report → {REPORT_JSON}")

    # Markdown report
    md = generate_markdown(summary, results, papers)
    with open(REPORT_MD, "w") as f:
        f.write(md)
    print(f"Markdown report → {REPORT_MD}")


if __name__ == "__main__":
    main()

