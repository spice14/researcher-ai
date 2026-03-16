"""Generate a human-readable benchmark report from integrity test results.

Reads outputs/ingestion_integrity_report.json and produces:
  - reports/ingestion_integrity_report.md   — full markdown report
  - Console summary

Run:
    python -m html_ingestion_poc.evaluation.generate_benchmark_report
    python -m html_ingestion_poc.evaluation.generate_benchmark_report --input path/to/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _load_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _generate_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append("# Ingestion Integrity Benchmark Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Papers tested:** {report['total_papers']}")
    lines.append(f"**Successful:** {report['successful']}")
    lines.append(f"**Failed:** {report['failed']}")
    lines.append(f"**Success rate:** {report['success_rate_pct']}%")
    lines.append(f"**Total time:** {report['total_time_s']}s")
    lines.append("")

    # --- Summary by category ---
    lines.append("## Results by Category")
    lines.append("")

    categories: Dict[str, list] = {}
    for m in report["metrics"]:
        categories.setdefault(m["category"], []).append(m)

    lines.append("| Category | Tested | Passed | Failed | Rate | Avg Time |")
    lines.append("|----------|--------|--------|--------|------|----------|")

    for cat in sorted(categories):
        metrics = categories[cat]
        ok = sum(1 for m in metrics if m["extraction_success"])
        fail = len(metrics) - ok
        rate = f"{ok / len(metrics) * 100:.0f}%"
        avg_time = f"{sum(m['extraction_time_s'] for m in metrics) / len(metrics):.1f}s"
        lines.append(f"| {cat} | {len(metrics)} | {ok} | {fail} | {rate} | {avg_time} |")

    lines.append("")

    # --- Detailed per-paper results ---
    lines.append("## Per-Paper Results")
    lines.append("")
    lines.append("| # | ID | Category | Status | Source | Words | Sections | Tables | Refs | Time |")
    lines.append("|---|-------|----------|--------|--------|-------|----------|--------|------|------|")

    for i, m in enumerate(report["metrics"], 1):
        status = "✅" if m["extraction_success"] else "❌"
        lines.append(
            f"| {i} | `{m['identifier']}` | {m['category']} | {status} | "
            f"{m['source_type']} | {m['word_count']} | {m['sections_count']} | "
            f"{m['tables_count']} | {m['references_count']} | {m['extraction_time_s']}s |"
        )

    lines.append("")

    # --- Content quality metrics ---
    successful = [m for m in report["metrics"] if m["extraction_success"]]
    if successful:
        lines.append("## Content Quality Summary")
        lines.append("")

        total_words = sum(m["word_count"] for m in successful)
        total_sections = sum(m["sections_count"] for m in successful)
        total_tables = sum(m["tables_count"] for m in successful)
        total_refs = sum(m["references_count"] for m in successful)
        with_title = sum(1 for m in successful if m["title_present"])
        with_abstract = sum(1 for m in successful if m["abstract_length"] > 50)
        with_sections = sum(1 for m in successful if m["sections_count"] > 0)

        lines.append(f"- **Total words extracted:** {total_words:,}")
        lines.append(f"- **Average words/paper:** {total_words // len(successful):,}")
        lines.append(f"- **Total sections:** {total_sections}")
        lines.append(f"- **Total tables:** {total_tables}")
        lines.append(f"- **Total references:** {total_refs}")
        lines.append(f"- **Papers with title:** {with_title}/{len(successful)}")
        lines.append(f"- **Papers with abstract (>50 chars):** {with_abstract}/{len(successful)}")
        lines.append(f"- **Papers with sections:** {with_sections}/{len(successful)}")
        lines.append("")

    # --- Cross-validation ---
    cross_vals = report.get("cross_validations", [])
    if cross_vals:
        lines.append("## Cross-Validation: HTML vs PDF")
        lines.append("")
        lines.append("| Paper | HTML Words | PDF Words | HTML Sections | PDF Sections | HTML Tables | PDF Tables |")
        lines.append("|-------|-----------|-----------|---------------|--------------|-------------|------------|")

        for cv in cross_vals:
            lines.append(
                f"| `{cv['identifier']}` | {cv['html_word_count']} | {cv['pdf_word_count']} | "
                f"{cv['html_sections']} | {cv['pdf_sections']} | "
                f"{cv['html_tables']} | {cv['pdf_tables']} |"
            )
        lines.append("")

        # Compute averages
        html_ok = [cv for cv in cross_vals if cv["html_success"]]
        pdf_ok = [cv for cv in cross_vals if cv["pdf_success"]]
        if html_ok and pdf_ok:
            avg_html_w = sum(cv["html_word_count"] for cv in html_ok) // len(html_ok)
            avg_pdf_w = sum(cv["pdf_word_count"] for cv in pdf_ok) // len(pdf_ok)
            lines.append(f"**Average HTML words:** {avg_html_w:,} | **Average PDF words:** {avg_pdf_w:,}")
            if avg_pdf_w > 0:
                ratio = avg_html_w / avg_pdf_w
                lines.append(f"**HTML/PDF word ratio:** {ratio:.2f}x")
            lines.append("")

    # --- Failures ---
    failures = [m for m in report["metrics"] if not m["extraction_success"]]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for m in failures:
            lines.append(f"### `{m['identifier']}` ({m['category']})")
            lines.append(f"- **Description:** {m['description']}")
            lines.append(f"- **Error:** {m['error']}")
            lines.append("")

    # --- Architecture notes ---
    lines.append("## Pipeline Architecture")
    lines.append("")
    lines.append("```")
    lines.append("Identifier → SourceResolver → ResolvedSource")
    lines.append("                                    │")
    lines.append("                          ┌─────────┴──────────┐")
    lines.append("                     HTMLExtractor         PDFFallback")
    lines.append("                     (arxiv/pmc/acl/       (pymupdf/")
    lines.append("                      generic)              docling)")
    lines.append("                          └─────────┬──────────┘")
    lines.append("                                    │")
    lines.append("                          MetadataEnricher")
    lines.append("                          (S2 / OpenAlex / Crossref)")
    lines.append("                                    │")
    lines.append("                          ResearchDocument")
    lines.append("                                    │")
    lines.append("                   ┌────────────────┼────────────────┐")
    lines.append("              to_markdown()    to_ingestion_result()  PaperStore")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark report from integrity test results")
    parser.add_argument("--input", type=Path, default=Path("outputs/ingestion_integrity_report.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Report not found: {args.input}")
        print("Run the integrity test first:")
        print("  python -m html_ingestion_poc.evaluation.ingestion_integrity_test")
        sys.exit(1)

    report = _load_report(args.input)
    markdown = _generate_markdown(report)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "ingestion_integrity_report.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Report written to {out_path}")
    print(f"  {report['successful']}/{report['total_papers']} passed ({report['success_rate_pct']}%)")


if __name__ == "__main__":
    main()
