"""Paper ingestion orchestrator — top-level pipeline.

Resolution order:
  1. Resolve identifier → source URLs
  2. Attempt HTML extraction (publisher-specific)
  3. Fall back to PDF extraction if HTML fails
  4. Enrich with metadata APIs
  5. Return fully populated ResearchDocument

Usage:
    ingestor = PaperIngestor()
    doc = ingestor.ingest("2401.12345")          # arXiv ID
    doc = ingestor.ingest("PMC1234567")           # PMC ID
    doc = ingestor.ingest("10.1234/example.2024") # DOI
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from html_ingestion_poc.ingestion.html_extractor import HTMLExtractor
from html_ingestion_poc.ingestion.metadata_enrichment import MetadataEnricher
from html_ingestion_poc.ingestion.pdf_fallback import PDFFallback
from html_ingestion_poc.ingestion.source_resolver import ResolvedSource, SourceResolver
from html_ingestion_poc.models.research_document import ResearchDocument

logger = logging.getLogger(__name__)


class PaperIngestor:
    """Orchestrate the full paper ingestion pipeline."""

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        skip_enrichment: bool = False,
        use_docling: bool = False,
    ):
        self._resolver = SourceResolver()
        self._html = HTMLExtractor()
        self._enricher = MetadataEnricher()
        self._pdf_fallback = PDFFallback(use_docling=use_docling)
        self._skip_enrichment = skip_enrichment
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, identifier: str) -> ResearchDocument:
        """Ingest a paper by identifier.

        Args:
            identifier: arXiv ID, PMC ID, ACL ID, DOI, or URL.

        Returns:
            Fully populated ResearchDocument.

        Raises:
            ValueError: If identifier cannot be resolved.
            RuntimeError: If both HTML and PDF extraction fail.
        """
        # Check cache
        cached = self._load_cache(identifier)
        if cached:
            logger.info("Cache hit for %s", identifier)
            return cached

        # Resolve
        resolved = self._resolver.resolve(identifier)
        logger.info("Resolved %s → %s (html=%s, pdf=%s)",
                     identifier, resolved.identifier_type.value,
                     resolved.html_url, resolved.pdf_url)

        # Extract
        doc = self._try_extract(resolved)

        # Enrich
        if not self._skip_enrichment:
            try:
                self._enricher.enrich(doc)
            except Exception as exc:
                logger.warning("Metadata enrichment failed for %s: %s", identifier, exc)

        # Cache
        self._save_cache(identifier, doc)
        return doc

    def _try_extract(self, resolved: ResolvedSource) -> ResearchDocument:
        """Attempt HTML extraction, fall back to PDF."""
        html_error: Optional[Exception] = None
        pdf_error: Optional[Exception] = None

        # Try HTML first
        if resolved.html_url:
            try:
                doc = self._html.extract(resolved)
                if doc.raw_text and len(doc.raw_text.strip()) > 2000:
                    logger.info("HTML extraction succeeded for %s (%d chars)",
                                resolved.identifier, len(doc.raw_text))
                    return doc
                logger.warning("HTML extraction returned too little text for %s, trying PDF",
                               resolved.identifier)
            except Exception as exc:
                html_error = exc
                logger.warning("HTML extraction failed for %s: %s", resolved.identifier, exc)

        # Try PDF fallback
        if resolved.pdf_url:
            try:
                doc = self._pdf_fallback.extract(resolved)
                logger.info("PDF fallback succeeded for %s (%d chars)",
                            resolved.identifier, len(doc.raw_text))
                return doc
            except Exception as exc:
                pdf_error = exc
                logger.warning("PDF fallback failed for %s: %s", resolved.identifier, exc)

        # Both failed
        msgs = []
        if html_error:
            msgs.append(f"HTML: {html_error}")
        elif not resolved.html_url:
            msgs.append("HTML: no URL available")
        if pdf_error:
            msgs.append(f"PDF: {pdf_error}")
        elif not resolved.pdf_url:
            msgs.append("PDF: no URL available")

        raise RuntimeError(
            f"All extraction methods failed for {resolved.identifier}: {'; '.join(msgs)}"
        )

    def _cache_key(self, identifier: str) -> str:
        return ResearchDocument.make_id(identifier)

    def _load_cache(self, identifier: str) -> Optional[ResearchDocument]:
        if not self._cache_dir:
            return None
        cache_file = self._cache_dir / f"{self._cache_key(identifier)}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return ResearchDocument.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to load cache for %s: %s", identifier, exc)
            return None

    def _save_cache(self, identifier: str, doc: ResearchDocument) -> None:
        if not self._cache_dir:
            return
        cache_file = self._cache_dir / f"{self._cache_key(identifier)}.json"
        try:
            cache_file.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
            logger.debug("Cached %s → %s", identifier, cache_file)
        except Exception as exc:
            logger.warning("Failed to cache %s: %s", identifier, exc)
