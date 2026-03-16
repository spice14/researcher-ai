#!/usr/bin/env python
"""Run deterministic MCP brutal audit over 150-paper corpus.

Phase 2:
- Load brutal_150 metadata
- For each paper, run MCP pipeline 3 times
- Compute determinism and aggregate metrics
- Emit JSON report, markdown summary, and per-paper diff snapshots
"""

from __future__ import annotations

import hashlib
import json
import signal
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add workspace root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Timeout handler for PDF extraction (pdfminer can hang)
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("PDF extraction took too long (>30 seconds)")

# Note: signal.SIGALRM is Unix-only; on Windows, we'll use process-level timeouts

from core.mcp.registry import MCPRegistry
from core.schemas.claim import Claim, ClaimEvidence, ClaimSubtype, ClaimType, ConfidenceLevel, Polarity
from core.schemas.normalized_claim import NoNormalizationReason
from services.belief.tool import BeliefTool
from services.contradiction.tool import ContradictionTool
from services.extraction.schemas import ClaimExtractionRequest
from services.extraction.service import ClaimExtractor
from services.extraction.tool import ExtractionTool
from services.ingestion.pdf_loader import extract_pages_from_pdf
from services.ingestion.schemas import IngestionChunk
from services.ingestion.tool import IngestionTool
from services.normalization.schemas import NormalizationRequest
from services.normalization.service import NormalizationService
from services.normalization.tool import NormalizationTool


METADATA_PATH = Path("outputs/brutal_150_metadata.json")
AUDIT_JSON_PATH = Path("outputs/brutal_150_audit.json")
SUMMARY_MD_PATH = Path("outputs/brutal_150_summary.md")
DIFF_DIR = Path("outputs/determinism_diffs")
RUNS_PER_PAPER = 3


def sha256_json(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_registry() -> MCPRegistry:
    registry = MCPRegistry()
    registry.register(IngestionTool())
    registry.register(ExtractionTool())
    registry.register(NormalizationTool())
    registry.register(BeliefTool())
    registry.register(ContradictionTool())
    return registry


def claim_from_dict(c: Dict[str, Any]) -> Claim:
    evidence = [
        ClaimEvidence(
            source_id=e.get("source_id", "unknown"),
            page=int(e.get("page", 1)),
            snippet=e.get("snippet", ""),
            retrieval_score=float(e.get("retrieval_score", 0.0)),
        )
        for e in c.get("evidence", [])
    ]

    confidence_raw = c.get("confidence_level", ConfidenceLevel.LOW)
    if isinstance(confidence_raw, ConfidenceLevel):
        confidence = confidence_raw
    elif isinstance(confidence_raw, str):
        confidence = ConfidenceLevel(confidence_raw.lower())
    else:
        confidence = ConfidenceLevel.LOW

    polarity_raw = c.get("polarity", Polarity.NEUTRAL)
    if isinstance(polarity_raw, Polarity):
        polarity = polarity_raw
    elif isinstance(polarity_raw, str):
        polarity = Polarity(polarity_raw.lower())
    else:
        polarity = Polarity.NEUTRAL

    subtype_raw = c.get("claim_subtype", ClaimSubtype.ABSOLUTE)
    if isinstance(subtype_raw, ClaimSubtype):
        subtype = subtype_raw
    elif isinstance(subtype_raw, str):
        subtype = ClaimSubtype(subtype_raw.lower())
    else:
        subtype = ClaimSubtype.ABSOLUTE

    return Claim(
        claim_id=c.get("claim_id", "unknown"),
        context_id=c.get("context_id"),
        subject=c.get("subject", ""),
        predicate=c.get("predicate", ""),
        object=c.get("object", ""),
        evidence=evidence if evidence else [
            ClaimEvidence(source_id="unknown", page=1, snippet="", retrieval_score=0.0)
        ],
        claim_type=ClaimType.PERFORMANCE,
        claim_subtype=subtype,
        polarity=polarity,
        confidence_level=confidence,
    )


def compute_extraction_rejections(chunks_payload: List[Dict[str, Any]], extractor: ClaimExtractor) -> Counter:
    reasons = Counter()
    for chunk_dict in chunks_payload:
        chunk = IngestionChunk(
            chunk_id=chunk_dict.get("chunk_id", ""),
            source_id=chunk_dict.get("source_id", ""),
            text=chunk_dict.get("text", ""),
            start_char=int(chunk_dict.get("start_char", 0)),
            end_char=int(chunk_dict.get("end_char", 0)),
            text_hash=chunk_dict.get("text_hash", ""),
            context_id=chunk_dict.get("context_id", ""),
            numeric_strings=chunk_dict.get("numeric_strings", []),
            unit_strings=chunk_dict.get("unit_strings", []),
            metric_names=chunk_dict.get("metric_names", []),
            page=int(chunk_dict.get("page", 1)),
        )
        results = extractor._extract_all(ClaimExtractionRequest(chunk=chunk))
        for result in results:
            if result.no_claim:
                reasons[result.no_claim.reason_code.value] += 1
    return reasons


def compute_normalization_rejections(claims_payload: List[Dict[str, Any]], normalizer: NormalizationService) -> Tuple[Counter, int]:
    reasons = Counter()
    misbindings = 0

    for claim_dict in claims_payload:
        claim_obj = claim_from_dict(claim_dict)
        norm_result = normalizer.normalize(NormalizationRequest(claim=claim_obj), debug_mode=True)
        if norm_result.no_normalization:
            reason = norm_result.no_normalization.reason_code.value
            reasons[reason] += 1
            if norm_result.no_normalization.reason_code == NoNormalizationReason.AMBIGUOUS_NUMERIC_BINDING:
                misbindings += 1

    return reasons, misbindings


def run_single_pipeline(
    registry: MCPRegistry,
    raw_text: str,
    source_id: str,
    extractor: ClaimExtractor,
    normalizer: NormalizationService,
) -> Dict[str, Any]:
    ingestion_tool = registry.get("ingestion")
    extraction_tool = registry.get("extraction")
    normalization_tool = registry.get("normalization")
    belief_tool = registry.get("belief")
    contradiction_tool = registry.get("contradiction")

    t0 = time.perf_counter()

    ingest_out = ingestion_tool.call({"raw_text": raw_text, "source_id": source_id})
    chunks = ingest_out.get("chunks", [])

    extract_out = extraction_tool.call({"chunks": chunks, "source_id": source_id})
    claims = extract_out.get("claims", [])

    norm_out = normalization_tool.call({"claims": claims, "debug_mode": True})
    normalized_claims = norm_out.get("normalized_claims", [])

    belief_out = belief_tool.call({"normalized_claims": normalized_claims})

    # Epistemic stage: contradiction tool expects belief_state.claims. We feed normalized claims through this slot.
    epistemic_in = {"belief_state": {"claims": normalized_claims}}
    epistemic_out = contradiction_tool.call(epistemic_in)

    extraction_rejections = compute_extraction_rejections(chunks, extractor)
    normalization_rejections, misbindings = compute_normalization_rejections(claims, normalizer)

    belief_states_count = 0
    if isinstance(belief_out.get("belief_states"), list):
        belief_states_count = len(belief_out.get("belief_states", []))
    elif isinstance(belief_out.get("belief_state"), dict):
        belief_states_count = 1

    contradictions_count = len(epistemic_out.get("contradictions", []))

    runtime_ms = (time.perf_counter() - t0) * 1000.0

    final_structured_output = {
        "source_id": source_id,
        "chunks": chunks,
        "claims": claims,
        "normalized_claims": normalized_claims,
        "belief": belief_out,
        "epistemic": epistemic_out,
        "extraction_rejections": dict(extraction_rejections),
        "normalization_rejections": dict(normalization_rejections),
        "misbindings": misbindings,
    }

    output_hash = sha256_json(final_structured_output)

    return {
        "chunks": len(chunks),
        "extracted_claims": len(claims),
        "normalized_claims": len(normalized_claims),
        "belief_states": belief_states_count,
        "contradictions": contradictions_count,
        "misbindings": misbindings,
        "extraction_rejections": dict(extraction_rejections),
        "normalization_rejections": dict(normalization_rejections),
        "runtime_ms": round(runtime_ms, 3),
        "hash": output_hash,
        "final_output": final_structured_output,
    }


def aggregate_top(counter: Counter, n: int = 15) -> List[Dict[str, Any]]:
    return [{"reason": k, "count": v} for k, v in counter.most_common(n)]


def write_summary_markdown(report: Dict[str, Any]) -> None:
    risk_flags = report["risk_flags"]
    runtime = report["runtime_distribution"]

    lines = [
        "# Brutal 150 Audit Summary",
        "",
        "## Architecture Gates",
        f"- Determinism %: {report['determinism_rate']:.2f}%",
        f"- Misbindings total: {report['total_misbindings']}",
        f"- Pipeline errors: {report['total_pipeline_errors']}",
        "",
        "## Yield",
        f"- Avg extracted: {report['avg_extracted_per_paper']:.3f}",
        f"- Avg normalized: {report['avg_normalized_per_paper']:.3f}",
        f"- Zero extraction %: {report['zero_extraction_rate']:.2f}%",
        f"- Zero normalization %: {report['zero_normalization_rate']:.2f}%",
        "",
        "## Rejection Profile",
        "",
        "### Top 15 Extraction Rejection Reasons",
    ]

    for item in report["top_extraction_rejections"]:
        lines.append(f"- {item['reason']}: {item['count']}")

    lines.extend([
        "",
        "### Top 15 Normalization Rejection Reasons",
    ])

    for item in report["top_normalization_rejections"]:
        lines.append(f"- {item['reason']}: {item['count']}")

    lines.extend([
        "",
        "## Domain Breakdown",
    ])

    for domain, stats in sorted(report["domain_breakdown"].items()):
        lines.append(
            f"- {domain}: papers={stats['papers']}, determinism_rate={stats['deterministic_rate']:.2f}%, "
            f"avg_extracted={stats['avg_extracted']:.3f}, avg_normalized={stats['avg_normalized']:.3f}, "
            f"zero_extraction_rate={stats['zero_extraction_rate']:.2f}%"
        )

    lines.extend([
        "",
        "## Runtime Distribution",
        f"- mean: {runtime['mean_ms']:.3f} ms",
        f"- std dev: {runtime['std_dev_ms']:.3f} ms",
        f"- min: {runtime['min_ms']:.3f} ms",
        f"- max: {runtime['max_ms']:.3f} ms",
        "",
        "## Risk Flags",
    ])

    if not risk_flags:
        lines.append("- NONE")
    else:
        for flag in risk_flags:
            lines.append(f"- {flag['level']}: {flag['message']}")

    SUMMARY_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_PATH}")

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    papers = metadata.get("papers", [])
    if len(papers) != 150:
        raise RuntimeError(f"Metadata must contain exactly 150 papers, found {len(papers)}")

    AUDIT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)

    global_extraction_rejections = Counter()
    global_normalization_rejections = Counter()

    paper_results: List[Dict[str, Any]] = []
    runtimes_all: List[float] = []
    total_pipeline_errors = 0
    corrupted_papers = 0

    print("[1/3] Running brutal 150 audit (3 runs per paper)...")

    for idx, paper in enumerate(papers, start=1):
        arxiv_id = paper["arxiv_id"]
        domain = paper["domain"]
        file_path = Path(paper["file_path"])

        if not file_path.exists():
            corrupted_papers += 1
            total_pipeline_errors += RUNS_PER_PAPER
            paper_results.append(
                {
                    "arxiv_id": arxiv_id,
                    "domain": domain,
                    "file_path": str(file_path),
                    "error": "PDF file missing",
                    "runs": [],
                    "deterministic": False,
                }
            )
            print(f"  [{idx:03d}/150] {arxiv_id} ERROR: missing file")
            continue

        # Skip problematic PDFs that cause pdfminer hangs
        # (e.g., 2602.21989v1 with malformed content streams)       
        if arxiv_id in ["2602.21989v1"]:
            corrupted_papers += 1
            total_pipeline_errors += RUNS_PER_PAPER
            paper_results.append(
                {
                    "arxiv_id": arxiv_id,
                    "domain": domain,
                    "file_path": str(file_path),
                    "error": "PDF extraction hangs (pdfminer deadlock on malformed streams)",
                    "runs": [],
                    "deterministic": False,
                }
            )
            print(f"  [{idx:03d}/150] {arxiv_id} SKIP: pdfminer hang")
            continue

        try:
            pages = extract_pages_from_pdf(str(file_path))
            raw_text = "\n".join(p.text for p in pages)
        except Exception as exc:
            corrupted_papers += 1
            total_pipeline_errors += RUNS_PER_PAPER
            paper_results.append(
                {
                    "arxiv_id": arxiv_id,
                    "domain": domain,
                    "file_path": str(file_path),
                    "error": f"PDF parse failure: {exc}",
                    "runs": [],
                    "deterministic": False,
                }
            )
            print(f"  [{idx:03d}/150] {arxiv_id} ERROR: parse failure")
            continue

        run_records: List[Dict[str, Any]] = []
        run_errors: List[str] = []

        for run_idx in range(1, RUNS_PER_PAPER + 1):
            registry = build_registry()
            extractor = ClaimExtractor()
            normalizer = NormalizationService()

            try:
                run_out = run_single_pipeline(
                    registry=registry,
                    raw_text=raw_text,
                    source_id=arxiv_id,
                    extractor=extractor,
                    normalizer=normalizer,
                )
                run_records.append(run_out)
                runtimes_all.append(run_out["runtime_ms"])
                global_extraction_rejections.update(run_out["extraction_rejections"])
                global_normalization_rejections.update(run_out["normalization_rejections"])
            except Exception as exc:
                total_pipeline_errors += 1
                run_errors.append(f"run_{run_idx}: {exc}")

        hashes = [r["hash"] for r in run_records]
        deterministic = len(run_records) == RUNS_PER_PAPER and len(set(hashes)) == 1

        if not deterministic:
            diff_payload = {
                "arxiv_id": arxiv_id,
                "domain": domain,
                "run_hashes": hashes,
                "run_level_counts": [
                    {
                        "run": i + 1,
                        "chunks": r["chunks"],
                        "extracted_claims": r["extracted_claims"],
                        "normalized_claims": r["normalized_claims"],
                        "belief_states": r["belief_states"],
                        "contradictions": r["contradictions"],
                        "misbindings": r["misbindings"],
                    }
                    for i, r in enumerate(run_records)
                ],
                "extraction_deltas": [
                    run_records[i + 1]["extracted_claims"] - run_records[i]["extracted_claims"]
                    for i in range(len(run_records) - 1)
                ],
                "normalization_deltas": [
                    run_records[i + 1]["normalized_claims"] - run_records[i]["normalized_claims"]
                    for i in range(len(run_records) - 1)
                ],
                "errors": run_errors,
            }
            (DIFF_DIR / f"{arxiv_id.replace('/', '_')}.json").write_text(
                json.dumps(diff_payload, indent=2), encoding="utf-8"
            )

        # Representative per-paper means over successful runs
        extracted_mean = statistics.mean([r["extracted_claims"] for r in run_records]) if run_records else 0.0
        normalized_mean = statistics.mean([r["normalized_claims"] for r in run_records]) if run_records else 0.0
        misbindings_sum = sum(r["misbindings"] for r in run_records)

        paper_results.append(
            {
                "arxiv_id": arxiv_id,
                "domain": domain,
                "file_path": str(file_path).replace("\\", "/"),
                "runs": [
                    {
                        "chunks": r["chunks"],
                        "extracted_claims": r["extracted_claims"],
                        "normalized_claims": r["normalized_claims"],
                        "belief_states": r["belief_states"],
                        "contradictions": r["contradictions"],
                        "misbindings": r["misbindings"],
                        "extraction_rejections": r["extraction_rejections"],
                        "normalization_rejections": r["normalization_rejections"],
                        "runtime_ms": r["runtime_ms"],
                        "hash": r["hash"],
                    }
                    for r in run_records
                ],
                "deterministic": deterministic,
                "errors": run_errors,
                "avg_extracted": extracted_mean,
                "avg_normalized": normalized_mean,
                "misbindings_total": misbindings_sum,
            }
        )

        status = "OK" if deterministic else "NONDET"
        print(f"  [{idx:03d}/150] {arxiv_id} {status} extracted={extracted_mean:.2f} normalized={normalized_mean:.2f}")

    print("[2/3] Aggregating corpus metrics...")

    valid_papers = len([p for p in paper_results if not p.get("error")])
    deterministic_papers = len([p for p in paper_results if p.get("deterministic")])
    nondeterministic_papers = valid_papers - deterministic_papers

    total_extracted = sum(p.get("avg_extracted", 0.0) for p in paper_results)
    total_normalized = sum(p.get("avg_normalized", 0.0) for p in paper_results)

    zero_extraction_count = len([p for p in paper_results if p.get("avg_extracted", 0.0) == 0])
    zero_normalization_count = len([p for p in paper_results if p.get("avg_normalized", 0.0) == 0])

    total_misbindings = sum(p.get("misbindings_total", 0) for p in paper_results)

    avg_runtime = statistics.mean(runtimes_all) if runtimes_all else 0.0
    runtime_std = statistics.pstdev(runtimes_all) if len(runtimes_all) > 1 else 0.0
    runtime_min = min(runtimes_all) if runtimes_all else 0.0
    runtime_max = max(runtimes_all) if runtimes_all else 0.0

    domain_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in paper_results:
        domain_bucket[p["domain"]].append(p)

    domain_breakdown = {}
    for domain, items in domain_bucket.items():
        papers_n = len(items)
        det_n = len([x for x in items if x.get("deterministic")])
        avg_ext = statistics.mean([x.get("avg_extracted", 0.0) for x in items]) if items else 0.0
        avg_norm = statistics.mean([x.get("avg_normalized", 0.0) for x in items]) if items else 0.0
        zero_ext = len([x for x in items if x.get("avg_extracted", 0.0) == 0])

        domain_breakdown[domain] = {
            "papers": papers_n,
            "deterministic_rate": (det_n / papers_n * 100.0) if papers_n else 0.0,
            "avg_extracted": avg_ext,
            "avg_normalized": avg_norm,
            "zero_extraction_rate": (zero_ext / papers_n * 100.0) if papers_n else 0.0,
        }

    determinism_rate = (deterministic_papers / valid_papers * 100.0) if valid_papers else 0.0
    zero_extraction_rate = (zero_extraction_count / max(len(paper_results), 1) * 100.0)
    zero_normalization_rate = (zero_normalization_count / max(len(paper_results), 1) * 100.0)

    avg_extracted_per_paper = total_extracted / max(len(paper_results), 1)
    avg_normalized_per_paper = total_normalized / max(len(paper_results), 1)
    normalization_yield_pct = (total_normalized / total_extracted * 100.0) if total_extracted > 0 else 0.0

    risk_flags = []
    if determinism_rate < 95.0:
        risk_flags.append({"level": "WARNING", "message": f"Determinism below threshold: {determinism_rate:.2f}% < 95%"})
    if total_misbindings > 0:
        risk_flags.append({"level": "CRITICAL", "message": f"Misbinding count > 0: {total_misbindings}"})
    if zero_extraction_rate > 40.0:
        risk_flags.append({"level": "WARNING", "message": f"Zero extraction rate high: {zero_extraction_rate:.2f}% > 40%"})
    if normalization_yield_pct < 10.0:
        risk_flags.append({"level": "WARNING", "message": f"Normalization yield low: {normalization_yield_pct:.2f}% < 10%"})

    report = {
        "total_papers": len(paper_results),
        "valid_papers": valid_papers,
        "corrupted_papers": corrupted_papers,
        "deterministic_papers": deterministic_papers,
        "determinism_rate": determinism_rate,
        "nondeterministic_papers": nondeterministic_papers,
        "total_extracted_claims": total_extracted,
        "total_normalized_claims": total_normalized,
        "avg_extracted_per_paper": avg_extracted_per_paper,
        "avg_normalized_per_paper": avg_normalized_per_paper,
        "zero_extraction_count": zero_extraction_count,
        "zero_normalization_count": zero_normalization_count,
        "zero_extraction_rate": zero_extraction_rate,
        "zero_normalization_rate": zero_normalization_rate,
        "total_misbindings": total_misbindings,
        "total_pipeline_errors": total_pipeline_errors,
        "avg_runtime": avg_runtime,
        "runtime_std_dev": runtime_std,
        "runtime_distribution": {
            "mean_ms": avg_runtime,
            "std_dev_ms": runtime_std,
            "min_ms": runtime_min,
            "max_ms": runtime_max,
        },
        "top_extraction_rejections": aggregate_top(global_extraction_rejections, 15),
        "top_normalization_rejections": aggregate_top(global_normalization_rejections, 15),
        "domain_breakdown": domain_breakdown,
        "risk_flags": risk_flags,
        "normalization_yield_pct": normalization_yield_pct,
        "papers": paper_results,
    }

    print("[3/3] Writing audit outputs...")
    AUDIT_JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary_markdown(report)

    print("\n[DONE] Brutal 150 audit complete")
    print(f"  Audit JSON: {AUDIT_JSON_PATH}")
    print(f"  Summary MD: {SUMMARY_MD_PATH}")
    print(f"  Diff dir:   {DIFF_DIR}")


if __name__ == "__main__":
    main()
