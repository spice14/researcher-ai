"""PDF fallback pipeline — use existing extractors when HTML is unavailable.

Reuses the proven PyMuPDFExtractor and converts its ExtractionResult into
a ResearchDocument for pipeline compatibility.

Usage:
    fallback = PDFFallback()
    doc = fallback.extract(resolved_source)       # downloads PDF → extracts
    doc = fallback.extract_from_path(path, ident)  # from local file
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx

from html_ingestion_poc.ingestion.source_resolver import ResolvedSource
from html_ingestion_poc.models.research_document import (
    Figure,
    ResearchDocument,
    Section,
    SourceType,
    Table,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "ResearcherAI/0.1 (pdf-fallback; "
    "https://github.com/spice14/ScholarOS; research use only)"
)
_LAST_REQUEST_TS: float = 0.0
_MIN_INTERVAL: float = 1.0


def _download_pdf(url: str, dest: Path, *, timeout: float = 60.0) -> Path:
    """Download a PDF to dest with rate limiting."""
    global _LAST_REQUEST_TS
    elapsed = time.monotonic() - _LAST_REQUEST_TS
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    logger.info("Downloading PDF from %s", url)
    with httpx.stream(
        "GET",
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    ) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)
    _LAST_REQUEST_TS = time.monotonic()
    logger.info("PDF saved to %s (%.1f KB)", dest, dest.stat().st_size / 1024)
    return dest


class PDFFallback:
    """Extract structured content from PDFs using PyMuPDFExtractor."""

    def __init__(self, *, use_docling: bool = False):
        self._use_docling = use_docling
        self._extractor = self._create_extractor()

    def _create_extractor(self):
        """Lazy-import the appropriate extractor."""
        if self._use_docling:
            try:
                from researcher_ai.ingestion.docling_extractor import DoclingExtractor
                return DoclingExtractor()
            except ImportError:
                logger.warning("Docling not available, falling back to PyMuPDF")

        from researcher_ai.ingestion.pymupdf_extractor import PyMuPDFExtractor
        return PyMuPDFExtractor()

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        """Download PDF and extract into ResearchDocument.

        Raises ValueError if no PDF URL is available.
        Raises httpx.HTTPStatusError on download failure.
        """
        if not resolved.pdf_url:
            raise ValueError(f"No PDF URL for identifier: {resolved.identifier}")

        with tempfile.TemporaryDirectory(prefix="researcher_ai_") as tmpdir:
            pdf_path = Path(tmpdir) / "paper.pdf"
            _download_pdf(resolved.pdf_url, pdf_path)
            return self.extract_from_path(pdf_path, resolved.identifier)

    def extract_from_path(self, pdf_path: Path, identifier: str) -> ResearchDocument:
        """Extract from a local PDF file."""
        logger.info("PDF extraction [%s] for %s from %s", self._extractor.name, identifier, pdf_path)

        result = self._extractor.extract(str(pdf_path))

        source_type = SourceType.PDF_DOCLING if self._use_docling else SourceType.PDF_PYMUPDF

        sections = [
            Section(
                title=s.title,
                level=getattr(s, "level", 1),
                content=getattr(s, "content", getattr(s, "text", "")),
                page=getattr(s, "page", None),
            )
            for s in result.sections
        ]

        tables = [
            Table(
                markdown=getattr(t, "markdown", t.content if hasattr(t, "content") else str(t)),
                caption=getattr(t, "caption", None),
                rows=getattr(t, "rows", 0),
                cols=getattr(t, "cols", 0),
                page=getattr(t, "page", None),
            )
            for t in result.tables
        ]

        figures = [
            Figure(
                caption=getattr(f, "caption", None),
                url=None,
                page=getattr(f, "page", None),
            )
            for f in result.figures
        ]

        return ResearchDocument(
            id=ResearchDocument.make_id(identifier),
            title=result.title or "",
            authors=[],
            abstract="",
            sections=sections,
            tables=tables,
            figures=figures,
            references=[],
            source_type=source_type,
            source_url=str(pdf_path),
            raw_text=result.text,
            metadata={
                "extractor": result.extractor,
                "num_pages": result.num_pages,
            },
        )
