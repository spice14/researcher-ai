"""Unit tests for dual-source verification in paper ingestion.

Decision order:
    1. No PDF URL               → keep HTML
    2. HTML words ≤ 0           → keep HTML
    3. Section guard (< 3)      → force PDF (no probe needed)
    4. Quick PDF probe + scale  → estimate full PDF word count
    5. Reference guard          → force PDF if refs < 5 and est. PDF > 1500 words
    6. Content-parity ratio     → force PDF if HTML < 0.4 × estimated PDF words
    7. Keep HTML; store probe stats in metadata
"""

from __future__ import annotations

from researcher_ai.ingestion.paper_ingestor import PaperIngestor
from researcher_ai.ingestion.pdf_fallback import PDFProbeResult
from researcher_ai.ingestion.research_document import (
    Reference,
    ResearchDocument,
    Section,
    SourceType,
)
from researcher_ai.ingestion.source_resolver import IdentifierType, ResolvedSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(
    identifier: str,
    word_count: int,
    source_type: SourceType,
    *,
    num_sections: int = 3,
    num_refs: int = 0,
) -> ResearchDocument:
    return ResearchDocument(
        id=identifier,
        title="Test Paper",
        source_type=source_type,
        raw_text="word " * word_count,
        sections=[
            Section(title=f"Section {i}", level=1, content="body text content here")
            for i in range(num_sections)
        ],
        references=[
            Reference(raw=f"Author et al. 202{i}")
            for i in range(num_refs)
        ],
    )


def _make_probe(
    probe_words: int,
    *,
    probe_pages: int = 5,
    total_pages: int = 5,
) -> PDFProbeResult:
    """Create a probe result; estimated_total = probe_words/probe_pages*total_pages."""
    return PDFProbeResult(
        probe_words=probe_words,
        probe_pages=probe_pages,
        total_pages=total_pages,
    )


def _make_resolved(pdf_url: str | None = "https://example.org/paper.pdf") -> ResolvedSource:
    return ResolvedSource(
        identifier="test-id",
        identifier_type=IdentifierType.ARXIV,
        html_url="https://example.org/paper.html",
        pdf_url=pdf_url,
    )


# ---------------------------------------------------------------------------
# PDFProbeResult unit tests
# ---------------------------------------------------------------------------

def test_probe_result_estimated_total_words_scales_correctly():
    probe = PDFProbeResult(probe_words=300, probe_pages=5, total_pages=20)
    # 300 / 5 * 20 = 1200
    assert probe.estimated_total_words == 1200


def test_probe_result_estimated_total_words_zero_when_no_pages():
    probe = PDFProbeResult(probe_words=0, probe_pages=0, total_pages=0)
    assert probe.estimated_total_words == 0


def test_probe_result_full_document_sampled_returns_probe_words():
    # probe_pages == total_pages → no scaling
    probe = PDFProbeResult(probe_words=500, probe_pages=10, total_pages=10)
    assert probe.estimated_total_words == 500


# ---------------------------------------------------------------------------
# Rule 6: content-parity ratio
# ---------------------------------------------------------------------------

def test_dual_source_switches_to_pdf_when_html_too_short():
    """HTML 100 words, PDF est. 500 → ratio 0.20 < 0.40 → switch."""
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 100, SourceType.ARXIV_HTML, num_refs=10)
    pdf_doc = _make_doc("doc-pdf", 600, SourceType.PDF_PYMUPDF)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(500)  # estimated_total = 500

        def extract(self, _r):
            return pdf_doc

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is pdf_doc
    assert selected.source_type == SourceType.PDF_PYMUPDF
    assert selected.metadata["dual_source_switch_reason"] == "ratio"


def test_dual_source_keeps_html_when_ratio_is_sufficient():
    """HTML 220 words, PDF est. 500 → ratio 0.44 ≥ 0.40 → keep HTML."""
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 220, SourceType.ARXIV_HTML, num_refs=10)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(500)

        def extract(self, _r):
            raise AssertionError("extract must not be called when HTML passes ratio")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc
    assert selected.source_type == SourceType.ARXIV_HTML
    assert selected.metadata["dual_source_switch_reason"] == "none"


def test_dual_source_keeps_html_when_pdf_extract_fails_after_ratio_trigger():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 100, SourceType.ARXIV_HTML, num_refs=10)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(500)

        def extract(self, _r):
            raise RuntimeError("pdf extraction failed")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


# ---------------------------------------------------------------------------
# Rule 1: no PDF URL
# ---------------------------------------------------------------------------

def test_dual_source_keeps_html_when_no_pdf_url():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 120, SourceType.ARXIV_HTML)
    resolved = _make_resolved(pdf_url=None)

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            raise AssertionError("must not probe when no PDF URL")

        def extract(self, _r):
            raise AssertionError("must not extract when no PDF URL")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


# ---------------------------------------------------------------------------
# Rule 4 / probe failure
# ---------------------------------------------------------------------------

def test_dual_source_keeps_html_when_quick_probe_fails():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 120, SourceType.ARXIV_HTML)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            raise RuntimeError("network error during probe")

        def extract(self, _r):
            raise AssertionError("extract must not be called when probe fails")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


# ---------------------------------------------------------------------------
# Rule 3: section density guard
# ---------------------------------------------------------------------------

def test_dual_source_section_guard_forces_pdf():
    """HTML with 0 sections (landing page) triggers section guard → PDF."""
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 1000, SourceType.ARXIV_HTML, num_sections=0)
    pdf_doc = _make_doc("doc-pdf", 2000, SourceType.PDF_PYMUPDF)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            raise AssertionError("probe must not be called; section guard fires first")

        def extract(self, _r):
            return pdf_doc

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is pdf_doc


def test_dual_source_section_guard_keeps_html_on_pdf_failure():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 1000, SourceType.ARXIV_HTML, num_sections=1)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            raise AssertionError("probe must not be called")

        def extract(self, _r):
            raise RuntimeError("PDF extract failed")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


# ---------------------------------------------------------------------------
# Rule 5: reference guard
# ---------------------------------------------------------------------------

def test_dual_source_reference_guard_forces_pdf():
    """HTML with 0 refs and large PDF est. (2000 words) triggers ref guard."""
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 800, SourceType.ARXIV_HTML, num_refs=0)
    pdf_doc = _make_doc("doc-pdf", 3000, SourceType.PDF_PYMUPDF)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            # probe_words=1000, total_pages=10 → estimated_total = 2000
            return _make_probe(1000, probe_pages=5, total_pages=10)

        def extract(self, _r):
            return pdf_doc

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is pdf_doc
    assert selected.metadata["dual_source_switch_reason"] == "ref_guard"


def test_dual_source_reference_guard_skipped_with_sufficient_refs():
    """HTML with 10 refs bypasses ref guard even if PDF is large."""
    ingestor = PaperIngestor(skip_enrichment=True)
    # 900 / 2000 = 0.45 ≥ 0.40 → keeps HTML on ratio too
    html_doc = _make_doc("doc-html", 900, SourceType.ARXIV_HTML, num_refs=10)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(1000, probe_pages=5, total_pages=10)  # est. 2000

        def extract(self, _r):
            raise AssertionError("extract must not be called")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


def test_dual_source_reference_guard_not_triggered_when_pdf_too_small():
    """Ref guard only fires when est. PDF ≥ 1500; small PDFs don't count."""
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 250, SourceType.ARXIV_HTML, num_refs=0)
    resolved = _make_resolved()

    class _MockFallback:
        called = False

        def quick_word_count(self, _r, *, max_pages=5):
            # estimated_total = 500 (< 1500) → ref guard skipped
            return _make_probe(500, probe_pages=5, total_pages=5)

        def extract(self, _r):
            raise AssertionError("extract must not be called for small PDF")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    # 250 / 500 = 0.50 ≥ 0.40 → keeps HTML on ratio; ref guard not triggered
    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


def test_dual_source_reference_guard_keeps_html_on_pdf_failure():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 800, SourceType.ARXIV_HTML, num_refs=0)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(1000, probe_pages=5, total_pages=10)

        def extract(self, _r):
            raise RuntimeError("PDF extraction failed")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc


# ---------------------------------------------------------------------------
# Probe metadata caching
# ---------------------------------------------------------------------------

def test_probe_stats_stored_in_metadata_when_html_kept():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 300, SourceType.ARXIV_HTML, num_refs=10)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(300, probe_pages=5, total_pages=10)  # est. 600

        def extract(self, _r):
            raise AssertionError("extract must not be called")

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    # 300 / 600 = 0.50 ≥ 0.40 → keep HTML
    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is html_doc
    meta = selected.metadata
    assert meta["dual_source_probe_words"] == 300
    assert meta["dual_source_probe_pages"] == 5
    assert meta["dual_source_total_pages"] == 10
    assert meta["dual_source_estimated_total_words"] == 600
    assert meta["dual_source_html_words"] == 300
    assert meta["dual_source_switch_reason"] == "none"


def test_probe_stats_stored_in_metadata_when_pdf_chosen():
    ingestor = PaperIngestor(skip_enrichment=True)
    html_doc = _make_doc("doc-html", 100, SourceType.ARXIV_HTML, num_refs=10)
    pdf_doc = _make_doc("doc-pdf", 2000, SourceType.PDF_PYMUPDF)
    resolved = _make_resolved()

    class _MockFallback:
        def quick_word_count(self, _r, *, max_pages=5):
            return _make_probe(500, probe_pages=5, total_pages=5)  # est. 500

        def extract(self, _r):
            return pdf_doc

    ingestor._pdf_fallback = _MockFallback()  # type: ignore[attr-defined]

    # 100 / 500 = 0.20 < 0.40 → switch to PDF
    selected = ingestor._maybe_swap_to_pdf_via_dual_source(html_doc=html_doc, resolved=resolved)

    assert selected is pdf_doc
    meta = selected.metadata
    assert meta["dual_source_probe_words"] == 500
    assert meta["dual_source_estimated_total_words"] == 500
    assert meta["dual_source_html_words"] == 100
    assert meta["dual_source_switch_reason"] == "ratio"
