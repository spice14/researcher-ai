"""Real-paper E2E autopsy runner.

Runs ingestion -> extraction -> normalization -> belief per paper using real sources
(no prebuilt cache artifacts), then runs contradiction/consensus at corpus scope.

Outputs under outputs/E2EautopsyTest:
- 30 per-paper markdown reports
- 1 consolidated markdown report
- JSON artifacts for reproducibility and debugging
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure workspace root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mcp.registry import MCPRegistry
from html_ingestion_poc.ingestion.paper_ingestor import PaperIngestor
from services.belief.tool import BeliefTool
from services.contradiction.tool import ContradictionTool
from services.extraction.tool import ExtractionTool
from services.ingestion.tool import IngestionTool
from services.normalization.tool import NormalizationTool

OUTPUT_DIR = Path("outputs/E2EautopsyTest")
PER_PAPER_DIR = OUTPUT_DIR / "per_paper"


@dataclass(frozen=True)
class PaperCandidate:
    paper_id: str
    identifier: str
    publisher: str
    category: str


def _candidate_pool() -> List[PaperCandidate]:
    """Curated real-source pool spanning >=10 publishers.

    The runner keeps only papers that reach full-success criteria.
    """
    return [
        # arXiv (high-yield set)
        PaperCandidate("1706.03762", "1706.03762", "arxiv", "nlp_transformer"),
        PaperCandidate("1810.04805", "1810.04805", "arxiv", "nlp_pretraining"),
        PaperCandidate("2005.14165", "2005.14165", "arxiv", "llm_foundation"),
        PaperCandidate("2103.00020", "2103.00020", "arxiv", "multimodal"),
        PaperCandidate("2203.02155", "2203.02155", "arxiv", "alignment"),
        PaperCandidate("2204.02311", "2204.02311", "arxiv", "llm_scaling"),
        PaperCandidate("2205.01068", "2205.01068", "arxiv", "llm_open"),
        PaperCandidate("2206.07682", "2206.07682", "arxiv", "rlhf"),
        PaperCandidate("2210.11610", "2210.11610", "arxiv", "self_improve"),
        PaperCandidate("2211.01786", "2211.01786", "arxiv", "multilingual"),
        PaperCandidate("2305.10601", "2305.10601", "arxiv", "reasoning"),
        PaperCandidate("2310.06825", "2310.06825", "arxiv", "llm_efficiency"),
        PaperCandidate("1512.03385", "1512.03385", "arxiv", "vision_residual"),
        PaperCandidate("1409.1556", "1409.1556", "arxiv", "vision_convnet"),
        PaperCandidate("1605.07146", "1605.07146", "arxiv", "batch_norm"),
        PaperCandidate("1603.05027", "1603.05027", "arxiv", "inception"),
        PaperCandidate("1802.05365", "1802.05365", "arxiv", "nas"),
        PaperCandidate("1907.11692", "1907.11692", "arxiv", "efficientnet"),

        # ACL Anthology
        PaperCandidate("emnlp_2023_main_1", "2023.emnlp-main.1", "acl_anthology", "nlp_conference"),
        PaperCandidate("acl_2023_long_1", "2023.acl-long.1", "acl_anthology", "nlp_conference"),

        # PMC
        PaperCandidate("PMC6993921", "PMC6993921", "pmc", "biomedical"),
        PaperCandidate("PMC7029158", "PMC7029158", "pmc", "biomedical"),

        # Nature
        PaperCandidate("nature_alphafold", "10.1038/s41586-021-03819-2", "nature", "biology_ai"),
        PaperCandidate("nature_alphageometry", "10.1038/s41586-023-06747-5", "nature", "math_reasoning"),
        PaperCandidate("nature_gpt4", "https://www.nature.com/articles/s41586-024-07566-y", "nature", "llm_science"),

        # PMLR (direct PDF)
        PaperCandidate("pmlr_chen20j", "https://proceedings.mlr.press/v119/chen20j/chen20j.pdf", "pmlr", "representation_learning"),
        PaperCandidate("pmlr_he16", "https://proceedings.mlr.press/v48/he16.pdf", "pmlr", "vision_deep_learning"),

        # USENIX (direct PDF)
        PaperCandidate("usenix_osdi16_abadi", "https://www.usenix.org/system/files/conference/osdi16/osdi16-abadi.pdf", "usenix", "systems_ml"),

        # JMLR
        PaperCandidate("jmlr_bengio03", "https://www.jmlr.org/papers/v3/bengio03a.html", "jmlr", "representation_learning"),

        # bioRxiv
        PaperCandidate("biorxiv_transformer_bio", "https://www.biorxiv.org/content/10.1101/2020.12.15.422761v1", "biorxiv", "biology_ml"),

        # AAAI (direct PDF)
        PaperCandidate("aaai_4648", "https://ojs.aaai.org/index.php/AAAI/article/download/4648/4526", "aaai", "ai_conference"),

        # IJCAI (direct PDF)
        PaperCandidate("ijcai_2021_0104", "https://www.ijcai.org/proceedings/2021/0104.pdf", "ijcai", "ai_conference"),

        # Additional optional candidates if any core publishers fail
        PaperCandidate("plos_comp_bio", "https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003378", "plos", "computational_biology"),
        PaperCandidate("frontiers_fnins", "https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2018.00700/full", "frontiers", "neuroscience"),
        PaperCandidate("ijcai_2021_0012", "https://www.ijcai.org/proceedings/2021/0012.pdf", "ijcai", "ai_conference"),
        PaperCandidate("ijcai_2021_0048", "https://www.ijcai.org/proceedings/2021/0048.pdf", "ijcai", "ai_conference"),
    ]


def build_registry() -> MCPRegistry:
    registry = MCPRegistry()
    registry.register(IngestionTool())
    registry.register(ExtractionTool())
    registry.register(NormalizationTool())
    registry.register(BeliefTool())
    registry.register(ContradictionTool())
    return registry


def _run_step(registry: MCPRegistry, tool_name: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
    t0 = time.perf_counter()
    try:
        result = registry.get(tool_name).call(payload)
        return result, (time.perf_counter() - t0) * 1000, None
    except Exception as exc:
        return None, (time.perf_counter() - t0) * 1000, f"{type(exc).__name__}: {exc}"


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _outcome_from_steps(steps: Dict[str, Dict[str, Any]], normalized_count: int) -> str:
    for step_name in ("ingestion", "extraction", "normalization", "belief"):
        if steps.get(step_name, {}).get("status") == "error":
            return f"failed_at_{step_name}"
    if normalized_count <= 0:
        return "partial_success"
    return "success"


def _run_paper_pipeline(registry: MCPRegistry, candidate: PaperCandidate, raw_text: str, source_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    steps: Dict[str, Dict[str, Any]] = {}
    t0 = time.perf_counter()

    ing_res, ing_ms, ing_err = _run_step(registry, "ingestion", {"raw_text": raw_text, "source_id": source_id})
    chunks = ing_res.get("chunks", []) if ing_res else []
    steps["ingestion"] = {
        "status": "error" if ing_err else "success",
        "duration_ms": round(ing_ms, 1),
        "error": ing_err,
        "chunks": len(chunks),
        "warnings": ing_res.get("warnings", []) if ing_res else [],
    }

    ext_res = None
    claims = []
    ext_ms = 0.0
    ext_err = None
    if not ing_err:
        ext_res, ext_ms, ext_err = _run_step(registry, "extraction", {"chunks": chunks, "source_id": source_id})
        claims = ext_res.get("claims", []) if ext_res else []
    steps["extraction"] = {
        "status": "error" if ext_err else "success",
        "duration_ms": round(ext_ms, 1),
        "error": ext_err,
        "claims_extracted": len(claims),
        "discarded_claims": ext_res.get("discarded_claims", 0) if ext_res else 0,
    }

    norm_res = None
    normalized_claims: List[Dict[str, Any]] = []
    norm_ms = 0.0
    norm_err = None
    if not ing_err and not ext_err:
        norm_res, norm_ms, norm_err = _run_step(registry, "normalization", {"claims": claims})
        normalized_claims = norm_res.get("normalized_claims", []) if norm_res else []
    steps["normalization"] = {
        "status": "error" if norm_err else "success",
        "duration_ms": round(norm_ms, 1),
        "error": norm_err,
        "normalized_claims": len(normalized_claims),
        "failed_normalizations": len(norm_res.get("failed_normalizations", [])) if norm_res else 0,
    }

    bel_res = None
    bel_ms = 0.0
    bel_err = None
    if not ing_err and not ext_err and not norm_err:
        bel_res, bel_ms, bel_err = _run_step(registry, "belief", {"normalized_claims": normalized_claims})
    belief_state = bel_res.get("belief_state") if bel_res else None
    steps["belief"] = {
        "status": "error" if bel_err else "success",
        "duration_ms": round(bel_ms, 1),
        "error": bel_err,
        "belief_state_present": bool(belief_state),
        "belief_metric": belief_state.get("metric") if belief_state else None,
        "consensus_strength": belief_state.get("consensus_strength") if belief_state else None,
        "qualitative_confidence": belief_state.get("qualitative_confidence") if belief_state else None,
    }

    outcome = _outcome_from_steps(steps, len(normalized_claims))
    result = {
        "paper_id": candidate.paper_id,
        "identifier": candidate.identifier,
        "publisher": candidate.publisher,
        "category": candidate.category,
        "source_id": source_id,
        "outcome": outcome,
        "total_duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "steps": steps,
    }

    return result, normalized_claims


def _write_per_paper_report(result: Dict[str, Any], out_path: Path, corpus_contradiction_count: int, corpus_consensus_count: int) -> None:
    lines = []
    lines.append(f"# E2E Autopsy — {result['paper_id']}")
    lines.append("")
    lines.append(f"- Identifier: {result['identifier']}")
    lines.append(f"- Publisher: {result['publisher']}")
    lines.append(f"- Category: {result['category']}")
    lines.append(f"- Source ID: {result['source_id']}")
    lines.append(f"- Outcome: {result['outcome']}")
    lines.append(f"- Total Duration: {result['total_duration_ms']} ms")
    lines.append(f"- Corpus Contradictions involving this paper: {corpus_contradiction_count}")
    lines.append(f"- Corpus Consensus groups touching this paper: {corpus_consensus_count}")
    lines.append("")

    for step_name in ("ingestion", "extraction", "normalization", "belief"):
        step = result["steps"].get(step_name, {})
        lines.append(f"## {step_name.capitalize()}")
        lines.append(f"- Status: {step.get('status')}")
        lines.append(f"- Duration: {step.get('duration_ms')} ms")
        if step.get("error"):
            lines.append(f"- Error: {step.get('error')}")
        for key in (
            "chunks",
            "claims_extracted",
            "discarded_claims",
            "normalized_claims",
            "failed_normalizations",
            "belief_state_present",
            "belief_metric",
            "consensus_strength",
            "qualitative_confidence",
        ):
            if key in step:
                lines.append(f"- {key}: {step.get(key)}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def _publisher_counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in results:
        pub = r["publisher"]
        counts[pub] = counts.get(pub, 0) + 1
    return counts


def _select_target_subset(results: List[Dict[str, Any]], target_papers: int, min_publishers: int) -> Optional[List[Dict[str, Any]]]:
    """Select exactly target_papers while preserving publisher diversity.

    Strategy:
    1. Pick one strongest paper per publisher first (highest normalized claims)
    2. Fill remaining slots by normalized_claims desc then chunks desc
    """
    if len(results) < target_papers:
        return None

    by_pub: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_pub.setdefault(r["publisher"], []).append(r)

    if len(by_pub) < min_publishers:
        return None

    for pub in by_pub:
        by_pub[pub].sort(
            key=lambda x: (
                x["steps"]["normalization"].get("normalized_claims", 0),
                x["steps"]["ingestion"].get("chunks", 0),
            ),
            reverse=True,
        )

    chosen: List[Dict[str, Any]] = []
    used_ids: Set[str] = set()

    # Seed with one paper per publisher to preserve diversity
    for pub in sorted(by_pub.keys()):
        pick = by_pub[pub][0]
        chosen.append(pick)
        used_ids.add(pick["paper_id"])

    # Fill remaining slots with strongest remaining papers
    remaining: List[Dict[str, Any]] = []
    for papers in by_pub.values():
        for p in papers:
            if p["paper_id"] not in used_ids:
                remaining.append(p)

    remaining.sort(
        key=lambda x: (
            x["steps"]["normalization"].get("normalized_claims", 0),
            x["steps"]["ingestion"].get("chunks", 0),
        ),
        reverse=True,
    )

    need = target_papers - len(chosen)
    if need > 0:
        chosen.extend(remaining[:need])

    if len(chosen) != target_papers:
        return None

    final_pub_count = len({r["publisher"] for r in chosen})
    if final_pub_count < min_publishers:
        return None

    return chosen


def run(target_papers: int, min_publishers: int) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PER_PAPER_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous run artifacts so report counts reflect this run only.
    for md_file in PER_PAPER_DIR.glob("*.md"):
        md_file.unlink()
    for artifact in ("consolidated.md", "consolidated.json", "manifest.json"):
        path = OUTPUT_DIR / artifact
        if path.exists():
            path.unlink()

    registry = build_registry()
    ingestor = PaperIngestor(cache_dir=None, skip_enrichment=True, use_docling=False)

    candidates = _candidate_pool()
    accepted_results: List[Dict[str, Any]] = []
    normalized_by_paper: Dict[str, List[Dict[str, Any]]] = {}
    attempted: List[Dict[str, Any]] = []

    print(f"Candidates available: {len(candidates)}")
    for idx, candidate in enumerate(candidates, 1):
        # Stop only when both quantity and diversity gates are met.
        if len(accepted_results) >= target_papers and len(_publisher_counts(accepted_results)) >= min_publishers:
            break

        print(f"[{idx:02d}/{len(candidates)}] ingest {candidate.paper_id} ({candidate.publisher})")
        t0 = time.perf_counter()
        try:
            doc = ingestor.ingest(candidate.identifier)
        except Exception as exc:
            attempted.append(
                {
                    "paper_id": candidate.paper_id,
                    "publisher": candidate.publisher,
                    "identifier": candidate.identifier,
                    "status": "ingestion_source_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"  ✗ source ingestion error: {exc}")
            continue

        raw_text = (doc.raw_text or "").strip()
        if len(raw_text) < 1000:
            attempted.append(
                {
                    "paper_id": candidate.paper_id,
                    "publisher": candidate.publisher,
                    "identifier": candidate.identifier,
                    "status": "rejected_low_text",
                    "text_length": len(raw_text),
                }
            )
            print(f"  ✗ rejected (low text): len={len(raw_text)}")
            continue

        source_id = f"real_{_safe_name(candidate.paper_id)}"
        result, normalized_claims = _run_paper_pipeline(registry, candidate, raw_text, source_id)

        attempted.append(
            {
                "paper_id": candidate.paper_id,
                "publisher": candidate.publisher,
                "identifier": candidate.identifier,
                "status": result["outcome"],
                "normalized_claims": result["steps"]["normalization"]["normalized_claims"],
                "chunks": result["steps"]["ingestion"]["chunks"],
                "duration_ms": result["total_duration_ms"],
                "source_ingest_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
        )

        if result["outcome"] == "success":
            accepted_results.append(result)
            normalized_by_paper[candidate.paper_id] = normalized_claims
            print(
                f"  ✓ accepted success | chunks={result['steps']['ingestion']['chunks']} "
                f"claims={result['steps']['extraction']['claims_extracted']} "
                f"normalized={result['steps']['normalization']['normalized_claims']}"
            )
        else:
            print(
                f"  ⚠ not accepted ({result['outcome']}) | chunks={result['steps']['ingestion']['chunks']} "
                f"claims={result['steps']['extraction']['claims_extracted']} "
                f"normalized={result['steps']['normalization']['normalized_claims']}"
            )

    selected_results = _select_target_subset(accepted_results, target_papers, min_publishers)

    if not selected_results:
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "reason": "insufficient_full_success_papers_or_publisher_diversity",
            "target_papers": target_papers,
            "accepted_papers": len(accepted_results),
            "min_publishers": min_publishers,
            "accepted_publishers": len({r['publisher'] for r in accepted_results}),
            "attempted": attempted,
        }
        (OUTPUT_DIR / "consolidated.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (OUTPUT_DIR / "consolidated.md").write_text(
            "# E2E Autopsy Consolidated\n\n"
            f"Run failed: collected {len(accepted_results)}/{target_papers} full-success papers.\n",
            encoding="utf-8",
        )
        print("\nFAILED: could not satisfy full-success quantity and diversity gates.")
        return 2

    accepted_results = selected_results
    pub_counts = _publisher_counts(accepted_results)

    # Corpus-level contradiction/consensus (cross-paper)
    selected_paper_ids: Set[str] = {r["paper_id"] for r in accepted_results}
    all_normalized: List[Dict[str, Any]] = []
    claim_to_paper: Dict[str, str] = {}
    for paper_id, claims in normalized_by_paper.items():
        if paper_id not in selected_paper_ids:
            continue
        for claim in claims:
            all_normalized.append(claim)
            claim_to_paper[claim["claim_id"]] = paper_id

    contradiction_res, cont_ms, cont_err = _run_step(
        registry,
        "contradiction",
        {"normalized_claims": all_normalized},
    )
    if cont_err:
        print(f"\nFAILED: corpus contradiction stage error: {cont_err}")
        return 4

    contradictions = contradiction_res.get("contradictions", [])
    consensus_groups = contradiction_res.get("consensus_groups", [])

    contradiction_count_by_paper: Dict[str, int] = {r["paper_id"]: 0 for r in accepted_results}
    consensus_count_by_paper: Dict[str, int] = {r["paper_id"]: 0 for r in accepted_results}

    for c in contradictions:
        pa = claim_to_paper.get(c.get("claim_id_a", ""))
        pb = claim_to_paper.get(c.get("claim_id_b", ""))
        if pa:
            contradiction_count_by_paper[pa] += 1
        if pb:
            contradiction_count_by_paper[pb] += 1

    for g in consensus_groups:
        for claim_id in g.get("claim_ids", []):
            p = claim_to_paper.get(claim_id)
            if p:
                consensus_count_by_paper[p] += 1

    # Per-paper markdown reports (30)
    for r in accepted_results:
        paper_id = r["paper_id"]
        out_path = PER_PAPER_DIR / f"{_safe_name(paper_id)}.md"
        _write_per_paper_report(
            r,
            out_path,
            contradiction_count_by_paper.get(paper_id, 0),
            consensus_count_by_paper.get(paper_id, 0),
        )

    # Consolidated report (1)
    total_chunks = sum(r["steps"]["ingestion"].get("chunks", 0) for r in accepted_results)
    total_claims = sum(r["steps"]["extraction"].get("claims_extracted", 0) for r in accepted_results)
    total_normalized = sum(r["steps"]["normalization"].get("normalized_claims", 0) for r in accepted_results)
    total_ms = sum(r["total_duration_ms"] for r in accepted_results)

    consolidated = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "target_papers": target_papers,
        "papers": accepted_results,
        "publisher_counts": pub_counts,
        "metrics": {
            "total_chunks": total_chunks,
            "total_claims": total_claims,
            "total_normalized_claims": total_normalized,
            "total_corpus_contradictions": len(contradictions),
            "total_corpus_consensus_groups": len(consensus_groups),
            "contradiction_stage_ms": round(cont_ms, 1),
            "total_pipeline_ms": round(total_ms, 1),
            "avg_pipeline_ms": round(total_ms / max(1, len(accepted_results)), 1),
        },
        "attempted": attempted,
    }

    (OUTPUT_DIR / "consolidated.json").write_text(json.dumps(consolidated, indent=2), encoding="utf-8")

    lines = []
    lines.append("# E2E Autopsy Consolidated")
    lines.append("")
    lines.append(f"- Run at: {consolidated['run_at']}")
    lines.append(f"- Papers: {len(accepted_results)}")
    lines.append(f"- Unique publishers: {len(pub_counts)}")
    lines.append(f"- Total chunks: {total_chunks}")
    lines.append(f"- Total claims: {total_claims}")
    lines.append(f"- Total normalized claims: {total_normalized}")
    lines.append(f"- Corpus contradictions: {len(contradictions)}")
    lines.append(f"- Corpus consensus groups: {len(consensus_groups)}")
    lines.append("")
    lines.append("## Publisher Distribution")
    for pub, count in sorted(pub_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {pub}: {count}")
    lines.append("")
    lines.append("## Paper Outcomes")
    lines.append("| # | Paper | Publisher | Category | Chunks | Claims | Normalized | Contradictions* | Consensus* | Total ms |")
    lines.append("|---|-------|-----------|----------|--------|--------|------------|-----------------|------------|----------|")
    for i, r in enumerate(accepted_results, 1):
        pid = r["paper_id"]
        lines.append(
            f"| {i} | {pid} | {r['publisher']} | {r['category']} | "
            f"{r['steps']['ingestion'].get('chunks', 0)} | "
            f"{r['steps']['extraction'].get('claims_extracted', 0)} | "
            f"{r['steps']['normalization'].get('normalized_claims', 0)} | "
            f"{contradiction_count_by_paper.get(pid, 0)} | "
            f"{consensus_count_by_paper.get(pid, 0)} | "
            f"{r['total_duration_ms']} |"
        )
    lines.append("")
    lines.append("*Contradictions/Consensus are counted from corpus-level cross-paper analysis.")

    (OUTPUT_DIR / "consolidated.md").write_text("\n".join(lines), encoding="utf-8")

    # Autopsy manifest
    manifest = {
        "run_at": consolidated["run_at"],
        "reports_root": str(OUTPUT_DIR),
        "per_paper_reports": sorted([p.name for p in PER_PAPER_DIR.glob("*.md")]),
        "consolidated_report": "consolidated.md",
        "consolidated_json": "consolidated.json",
        "required_report_count": target_papers + 1,
        "actual_report_count": len(list(PER_PAPER_DIR.glob("*.md"))) + (1 if (OUTPUT_DIR / "consolidated.md").exists() else 0),
        "publishers": pub_counts,
        "unique_publishers": len(pub_counts),
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nSUCCESS")
    print(f"Reports: {manifest['actual_report_count']} (expected {manifest['required_report_count']})")
    print(f"Unique publishers: {manifest['unique_publishers']} (required >= {min_publishers})")
    print(f"Output dir: {OUTPUT_DIR}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-paper E2E autopsy")
    parser.add_argument("--target-papers", type=int, default=30)
    parser.add_argument("--min-publishers", type=int, default=10)
    args = parser.parse_args()

    code = run(target_papers=args.target_papers, min_publishers=args.min_publishers)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
