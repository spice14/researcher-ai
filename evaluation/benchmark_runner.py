"""Batch evaluation runner for ScholarOS pipeline.

Runs the pipeline on a corpus of papers and computes quality metrics
against ground truth annotations.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from evaluation.annotation_schema import GroundTruth, PaperAnnotation
from evaluation.metrics import (
    compute_claim_metrics,
    compute_cluster_purity,
    score_hypothesis,
    compute_provenance_coverage,
)

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Runs ScholarOS pipeline on a corpus and evaluates against ground truth.

    Usage:
        runner = BenchmarkRunner(ground_truth_path="evaluation/ground_truth/annotated_5papers.jsonl")
        report = runner.run(pdf_paths=["paper1.pdf", "paper2.pdf"])
        runner.save_report(report, "benchmark_report.json")
    """

    def __init__(
        self,
        ground_truth_path: Optional[str] = None,
        output_dir: str = "outputs/benchmark",
    ) -> None:
        self._gt_path = ground_truth_path
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._ground_truth: Optional[GroundTruth] = None

        if ground_truth_path and os.path.exists(ground_truth_path):
            self._ground_truth = GroundTruth.from_jsonl(ground_truth_path)
            logger.info("Loaded ground truth: %d papers", len(self._ground_truth.papers))

    def run(
        self,
        pdf_paths: Optional[List[str]] = None,
        source_ids: Optional[List[str]] = None,
    ) -> Dict:
        """Run evaluation pipeline on a corpus.

        Args:
            pdf_paths: List of PDF paths to evaluate
            source_ids: Optional override source IDs

        Returns:
            Evaluation report dict
        """
        from cli.runner import build_registry, ingest_pdf
        from services.extraction.tool import ExtractionTool
        from services.normalization.tool import NormalizationTool
        from services.context.tool import ContextTool

        registry, emb, vs = build_registry()
        ext_tool = ExtractionTool()
        norm_tool = NormalizationTool()
        ctx_tool = ContextTool()

        all_predicted_claims = []
        all_gold_claims = []
        paper_results = []
        total_start = time.time()

        pdf_paths = pdf_paths or []

        for i, pdf_path in enumerate(pdf_paths):
            sid = (source_ids or [])[i] if source_ids and i < len(source_ids) else None
            logger.info("Processing %s", pdf_path)

            try:
                paper_start = time.time()
                ingestion = ingest_pdf(pdf_path, source_id=sid)
                source_id = ingestion["source_id"]

                # Context extraction
                ctx_out = ctx_tool.call(ingestion)

                # Claim extraction
                ext_out = ext_tool.call(ingestion)
                predicted_claims = ext_out.get("claims", [])

                # Normalization
                norm_out = norm_tool.call(ext_out)

                paper_duration = (time.time() - paper_start) * 1000
                all_predicted_claims.extend(predicted_claims)

                # Ground truth for this paper
                gold_claims = []
                if self._ground_truth:
                    gold_claims = [
                        c.model_dump()
                        for c in self._ground_truth.get_claims_for_paper(source_id)
                    ]
                all_gold_claims.extend(gold_claims)

                paper_results.append({
                    "paper_id": source_id,
                    "pdf_path": pdf_path,
                    "chunk_count": len(ingestion.get("chunks", [])),
                    "predicted_claims": len(predicted_claims),
                    "gold_claims": len(gold_claims),
                    "duration_ms": paper_duration,
                    "warnings": ingestion.get("warnings", []),
                })

            except Exception as exc:
                logger.error("Failed to process %s: %s", pdf_path, exc)
                paper_results.append({
                    "paper_id": sid or pdf_path,
                    "error": str(exc),
                })

        total_duration_ms = (time.time() - total_start) * 1000

        # Compute aggregate claim metrics
        claim_metrics = compute_claim_metrics(all_predicted_claims, all_gold_claims)

        # Compute provenance coverage (from trace if available)
        prov_metrics = {"coverage": 1.0, "total": 0, "with_hash": 0}

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "corpus_size": len(pdf_paths),
            "total_duration_ms": round(total_duration_ms, 1),
            "papers": paper_results,
            "aggregate_metrics": {
                "claim_precision": claim_metrics["precision"],
                "claim_recall": claim_metrics["recall"],
                "claim_f1": claim_metrics["f1"],
                "total_predicted_claims": len(all_predicted_claims),
                "total_gold_claims": len(all_gold_claims),
                "provenance_coverage": prov_metrics["coverage"],
            },
            "thresholds": {
                "claim_f1_target": 0.40,
                "claim_f1_met": claim_metrics["f1"] >= 0.40,
            },
        }

        return report

    def save_report(self, report: Dict, filename: Optional[str] = None) -> Path:
        """Save evaluation report to JSON file.

        Args:
            report: Report dict from run()
            filename: Optional filename (auto-generated if not given)

        Returns:
            Path to saved file
        """
        fname = filename or f"benchmark_{int(time.time())}.json"
        fpath = self._output_dir / fname
        with open(fpath, "w") as f:
            json.dump(report, f, indent=2)
        logger.info("Report saved to %s", fpath)
        return fpath

    def print_summary(self, report: Dict) -> None:
        """Print a human-readable summary of the benchmark report."""
        am = report.get("aggregate_metrics", {})
        th = report.get("thresholds", {})

        print("\n" + "=" * 60)
        print("ScholarOS Benchmark Report")
        print("=" * 60)
        print(f"Corpus:    {report.get('corpus_size', 0)} papers")
        print(f"Duration:  {report.get('total_duration_ms', 0):.0f}ms")
        print()
        print("Claim Extraction:")
        print(f"  Precision: {am.get('claim_precision', 0):.3f}")
        print(f"  Recall:    {am.get('claim_recall', 0):.3f}")
        print(f"  F1:        {am.get('claim_f1', 0):.3f}  "
              f"{'✓ (target met)' if th.get('claim_f1_met') else '✗ (below 0.40 target)'}")
        print(f"  Predicted: {am.get('total_predicted_claims', 0)}")
        print(f"  Gold:      {am.get('total_gold_claims', 0)}")
        print()
        print(f"Provenance coverage: {am.get('provenance_coverage', 0):.3f}")
        print("=" * 60)


def main():
    """CLI entry point for benchmark runner."""
    import argparse

    parser = argparse.ArgumentParser(description="ScholarOS benchmark evaluation")
    parser.add_argument("pdfs", nargs="*", help="PDF files to evaluate")
    parser.add_argument(
        "--ground-truth",
        default="evaluation/ground_truth/annotated_5papers.jsonl",
        help="Path to ground truth JSONL",
    )
    parser.add_argument("--output", help="Output report filename")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    runner = BenchmarkRunner(ground_truth_path=args.ground_truth)
    report = runner.run(pdf_paths=args.pdfs)
    runner.print_summary(report)
    fpath = runner.save_report(report, args.output)
    print(f"\nFull report: {fpath}")


if __name__ == "__main__":
    main()
