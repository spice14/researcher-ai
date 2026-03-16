"""Ingestion integrity test — validate the pipeline against real papers.

Tests 30 papers across 7 publisher types:
  - arXiv (HTML)     — 8 papers
  - PMC (HTML)       — 5 papers
  - ACL Anthology    — 4 papers
  - DOI → publisher  — 4 papers (Nature, Science, IEEE, Springer)
  - PDF fallback     — 3 papers (arXiv PDFs for comparison)
  - Metadata-only    — 3 papers (DOIs, metadata enrichment validates)
  - Cross-validation — 3 papers (same paper, HTML vs PDF)

Metrics collected per paper:
  - extraction_success: bool
  - source_type: str
  - title_present: bool
  - authors_count: int
  - abstract_length: int
  - sections_count: int
  - tables_count: int
  - figures_count: int
  - references_count: int
  - raw_text_length: int
  - word_count: int
  - extraction_time_s: float
  - error: Optional[str]

Run:
    python -m html_ingestion_poc.evaluation.ingestion_integrity_test
    python -m html_ingestion_poc.evaluation.ingestion_integrity_test --quick  # 10 papers only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Test corpus — 30 papers across 7 publisher types
# ---------------------------------------------------------------------------

# Format: (identifier, expected_source, description)
ARXIV_HTML_PAPERS = [
    ("2401.02385", "arxiv", "Graph of Thoughts"),
    ("2310.06825", "arxiv", "Self-RAG"),
    ("2305.10601", "arxiv", "Tree of Thoughts"),
    ("2312.10997", "arxiv", "Mixture of Experts survey"),
    ("2402.13116", "arxiv", "LoRA learns less, forgets less"),
    ("2401.04088", "arxiv", "MoE-Mamba"),
    ("2305.14314", "arxiv", "QLoRA"),
    ("2307.09288", "arxiv", "Llama 2"),
]

PMC_PAPERS = [
    ("PMC7029158", "pmc", "COVID-19 identification CT"),
    ("PMC6993921", "pmc", "Drug repurposing review"),
    ("PMC7166335", "pmc", "COVID-19 clinical features"),
    ("PMC6517116", "pmc", "Deep learning medical imaging"),
    ("PMC7169933", "pmc", "COVID-19 aerosol transmission"),
]

ACL_PAPERS = [
    ("2023.acl-long.1", "acl", "ACL 2023 paper 1"),
    ("2023.emnlp-main.1", "acl", "EMNLP 2023 paper 1"),
    ("2023.findings-acl.1", "acl", "ACL Findings 2023 paper 1"),
    ("2024.naacl-long.1", "acl", "NAACL 2024 paper 1"),
]

DOI_PAPERS = [
    ("10.1038/s41586-021-03819-2", "doi", "AlphaFold Nature"),
    ("10.1126/science.abj8754", "doi", "AlphaFold Science"),
    ("10.1007/s10462-023-10386-z", "doi", "LLM survey Springer"),
    ("10.1109/TPAMI.2023.3280317", "doi", "Vision Transformer survey IEEE"),
]

PDF_FALLBACK_PAPERS = [
    ("2401.02385", "pdf_fallback", "Graph of Thoughts (PDF)"),
    ("2305.10601", "pdf_fallback", "Tree of Thoughts (PDF)"),
    ("2307.09288", "pdf_fallback", "Llama 2 (PDF)"),
]

METADATA_ONLY_PAPERS = [
    ("10.1038/s41586-023-06747-5", "metadata", "GPT-4 Nature"),
    ("10.1145/3442188.3445922", "metadata", "Stochastic Parrots ACM"),
    ("10.1126/science.aaa8685", "metadata", "Deep learning review Science"),
]

CROSS_VALIDATION_PAPERS = [
    ("2401.02385", "cross_val", "Graph of Thoughts — HTML vs PDF"),
    ("2305.14314", "cross_val", "QLoRA — HTML vs PDF"),
    ("2310.06825", "cross_val", "Self-RAG — HTML vs PDF"),
]

# Quick subset for fast iteration
QUICK_PAPERS = ARXIV_HTML_PAPERS[:3] + PMC_PAPERS[:2] + ACL_PAPERS[:2] + DOI_PAPERS[:1] + PDF_FALLBACK_PAPERS[:1] + METADATA_ONLY_PAPERS[:1]


@dataclass
class ExtractionMetric:
    """Metrics for a single paper extraction."""
    identifier: str
    description: str
    category: str
    extraction_success: bool = False
    source_type: str = ""
    title_present: bool = False
    title: str = ""
    authors_count: int = 0
    abstract_length: int = 0
    sections_count: int = 0
    tables_count: int = 0
    figures_count: int = 0
    references_count: int = 0
    raw_text_length: int = 0
    word_count: int = 0
    extraction_time_s: float = 0.0
    error: Optional[str] = None


@dataclass
class CrossValidationMetric:
    """Compare HTML vs PDF extraction for the same paper."""
    identifier: str
    description: str
    html_word_count: int = 0
    pdf_word_count: int = 0
    html_sections: int = 0
    pdf_sections: int = 0
    html_tables: int = 0
    pdf_tables: int = 0
    html_refs: int = 0
    pdf_refs: int = 0
    html_success: bool = False
    pdf_success: bool = False
    html_error: Optional[str] = None
    pdf_error: Optional[str] = None


@dataclass
class IntegrityReport:
    """Full suite report."""
    total_papers: int = 0
    successful: int = 0
    failed: int = 0
    metrics: List[ExtractionMetric] = field(default_factory=list)
    cross_validations: List[CrossValidationMetric] = field(default_factory=list)
    total_time_s: float = 0.0

    def success_rate(self) -> float:
        return self.successful / self.total_papers * 100 if self.total_papers else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_papers": self.total_papers,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate_pct": round(self.success_rate(), 1),
            "total_time_s": round(self.total_time_s, 1),
            "metrics": [asdict(m) for m in self.metrics],
            "cross_validations": [asdict(cv) for cv in self.cross_validations],
        }


def run_integrity_test(*, quick: bool = False, output_dir: Path = Path("outputs")) -> IntegrityReport:
    """Run the full integrity test suite."""
    # Lazy imports so the module can be imported without network
    from html_ingestion_poc.ingestion.html_extractor import HTMLExtractor
    from html_ingestion_poc.ingestion.metadata_enrichment import MetadataEnricher
    from html_ingestion_poc.ingestion.paper_ingestor import PaperIngestor
    from html_ingestion_poc.ingestion.pdf_fallback import PDFFallback
    from html_ingestion_poc.ingestion.source_resolver import SourceResolver
    from html_ingestion_poc.storage.paper_store import PaperStore

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("integrity_test")

    output_dir.mkdir(parents=True, exist_ok=True)
    store = PaperStore(base_dir=output_dir / "integrity_papers")
    resolver = SourceResolver()
    html_ext = HTMLExtractor()
    enricher = MetadataEnricher()
    pdf_fb = PDFFallback()
    ingestor = PaperIngestor(cache_dir=output_dir / "integrity_cache")

    report = IntegrityReport()
    start_time = time.monotonic()

    # Build paper list
    if quick:
        papers = QUICK_PAPERS
        logger.info("Quick mode — testing %d papers", len(papers))
    else:
        papers = (
            ARXIV_HTML_PAPERS + PMC_PAPERS + ACL_PAPERS +
            DOI_PAPERS + METADATA_ONLY_PAPERS
        )
        logger.info("Full mode — testing %d papers + %d PDF fallback + %d cross-validation",
                     len(papers), len(PDF_FALLBACK_PAPERS), len(CROSS_VALIDATION_PAPERS))

    # ---- Standard extraction tests ----
    for ident, category, desc in papers:
        report.total_papers += 1
        metric = ExtractionMetric(identifier=ident, description=desc, category=category)
        t0 = time.monotonic()

        try:
            doc = ingestor.ingest(ident)
            metric.extraction_success = True
            metric.source_type = doc.source_type.value
            metric.title_present = bool(doc.title)
            metric.title = doc.title[:100] if doc.title else ""
            metric.authors_count = len(doc.authors)
            metric.abstract_length = len(doc.abstract)
            metric.sections_count = len(doc.sections)
            metric.tables_count = len(doc.tables)
            metric.figures_count = len(doc.figures)
            metric.references_count = len(doc.references)
            metric.raw_text_length = len(doc.raw_text)
            metric.word_count = doc.word_count

            store.store(doc)
            report.successful += 1

        except Exception as exc:
            metric.error = str(exc)[:500]
            report.failed += 1
            logger.error("FAILED %s (%s): %s", ident, desc, exc)

        metric.extraction_time_s = round(time.monotonic() - t0, 2)
        report.metrics.append(metric)
        logger.info(
            "[%s] %s — %s | words=%d secs=%d tables=%d refs=%d",
            "OK" if metric.extraction_success else "FAIL",
            ident, desc, metric.word_count,
            metric.sections_count, metric.tables_count, metric.references_count,
        )

    # ---- PDF fallback tests ----
    if not quick:
        for ident, category, desc in PDF_FALLBACK_PAPERS:
            report.total_papers += 1
            metric = ExtractionMetric(identifier=ident, description=desc, category=category)
            t0 = time.monotonic()

            try:
                resolved = resolver.resolve(ident)
                doc = pdf_fb.extract(resolved)
                enricher.enrich(doc)
                metric.extraction_success = True
                metric.source_type = doc.source_type.value
                metric.title_present = bool(doc.title)
                metric.title = doc.title[:100] if doc.title else ""
                metric.authors_count = len(doc.authors)
                metric.abstract_length = len(doc.abstract)
                metric.sections_count = len(doc.sections)
                metric.tables_count = len(doc.tables)
                metric.raw_text_length = len(doc.raw_text)
                metric.word_count = doc.word_count
                store.store(doc)
                report.successful += 1

            except Exception as exc:
                metric.error = str(exc)[:500]
                report.failed += 1
                logger.error("FAILED PDF %s (%s): %s", ident, desc, exc)

            metric.extraction_time_s = round(time.monotonic() - t0, 2)
            report.metrics.append(metric)

    # ---- Cross-validation tests ----
    if not quick:
        for ident, _, desc in CROSS_VALIDATION_PAPERS:
            cv = CrossValidationMetric(identifier=ident, description=desc)

            # HTML extraction
            try:
                resolved = resolver.resolve(ident)
                html_doc = html_ext.extract(resolved)
                cv.html_success = True
                cv.html_word_count = html_doc.word_count
                cv.html_sections = len(html_doc.sections)
                cv.html_tables = len(html_doc.tables)
                cv.html_refs = len(html_doc.references)
            except Exception as exc:
                cv.html_error = str(exc)[:300]

            # PDF extraction
            try:
                pdf_doc = pdf_fb.extract(resolved)
                cv.pdf_success = True
                cv.pdf_word_count = pdf_doc.word_count
                cv.pdf_sections = len(pdf_doc.sections)
                cv.pdf_tables = len(pdf_doc.tables)
                cv.pdf_refs = len(pdf_doc.references)
            except Exception as exc:
                cv.pdf_error = str(exc)[:300]

            report.cross_validations.append(cv)

    report.total_time_s = round(time.monotonic() - start_time, 1)

    # Save report
    report_path = output_dir / "ingestion_integrity_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
    logger.info(
        "Integrity test complete: %d/%d passed (%.1f%%) in %.1fs → %s",
        report.successful, report.total_papers, report.success_rate(),
        report.total_time_s, report_path,
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper ingestion integrity test")
    parser.add_argument("--quick", action="store_true", help="Test 10 papers only")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Output directory")
    args = parser.parse_args()

    report = run_integrity_test(quick=args.quick, output_dir=args.output_dir)

    # Print summary table
    print("\n" + "=" * 80)
    print(f"INGESTION INTEGRITY TEST — {report.successful}/{report.total_papers} "
          f"passed ({report.success_rate():.1f}%) in {report.total_time_s:.1f}s")
    print("=" * 80)

    print(f"\n{'Category':<15} {'Success':<8} {'Total':<7} {'Rate':<7}")
    print("-" * 40)
    categories: Dict[str, list] = {}
    for m in report.metrics:
        categories.setdefault(m.category, []).append(m)
    for cat, metrics in sorted(categories.items()):
        ok = sum(1 for m in metrics if m.extraction_success)
        print(f"{cat:<15} {ok:<8} {len(metrics):<7} {ok / len(metrics) * 100:.0f}%")

    # Failures
    failures = [m for m in report.metrics if not m.extraction_success]
    if failures:
        print(f"\nFailed papers ({len(failures)}):")
        for m in failures:
            print(f"  [{m.category}] {m.identifier}: {m.error}")

    # Cross-validation summary
    if report.cross_validations:
        print(f"\nCross-validation (HTML vs PDF):")
        for cv in report.cross_validations:
            status = "✓" if cv.html_success and cv.pdf_success else "✗"
            print(f"  {status} {cv.identifier}: "
                  f"HTML {cv.html_word_count}w/{cv.html_sections}s/{cv.html_tables}t "
                  f"vs PDF {cv.pdf_word_count}w/{cv.pdf_sections}s/{cv.pdf_tables}t")

    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
