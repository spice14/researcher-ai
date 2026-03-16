"""Metadata enrichment via free academic APIs.

Supports three providers (all unauthenticated):
  - OpenAlex   (api.openalex.org)
  - Crossref   (api.crossref.org)
  - Semantic Scholar (api.semanticscholar.org)

Merges metadata into an existing ResearchDocument:
  title, authors, abstract, doi, year, references, venue, citation count.
Graceful degradation — API failures never crash the pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from html_ingestion_poc.models.research_document import Reference, ResearchDocument

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "ResearcherAI/0.1 (metadata-enrichment; "
    "https://github.com/spice14/researcher-ai; research use only; "
    "mailto:researcher-ai@example.com)"
)
_TIMEOUT = 10.0  # seconds
_LAST_REQUEST_TS: float = 0.0
_MIN_INTERVAL: float = 1.0


def _api_get(url: str, *, params: Optional[dict] = None) -> Optional[dict]:
    """Rate-limited JSON GET with graceful failure."""
    global _LAST_REQUEST_TS
    elapsed = time.monotonic() - _LAST_REQUEST_TS
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    try:
        logger.info("API GET %s params=%s", url, params)
        resp = httpx.get(
            url,
            params=params,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        _LAST_REQUEST_TS = time.monotonic()
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("API request failed for %s: %s", url, exc)
        return None


# --------------------------------------------------------------------------- #
# Individual providers
# --------------------------------------------------------------------------- #

class _OpenAlexProvider:
    """Fetch metadata from OpenAlex (free, no key required)."""

    BASE = "https://api.openalex.org/works"

    def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        data = _api_get(f"{self.BASE}/doi:{doi}")
        if not data:
            return None
        return self._normalize(data)

    def fetch_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        data = _api_get(self.BASE, params={"search": title, "per_page": "1"})
        if not data or not data.get("results"):
            return None
        return self._normalize(data["results"][0])

    @staticmethod
    def _normalize(work: dict) -> Dict[str, Any]:
        authors = []
        for authorship in work.get("authorships", []):
            name = authorship.get("author", {}).get("display_name")
            if name:
                authors.append(name)

        return {
            "title": work.get("title", ""),
            "authors": authors,
            "doi": work.get("doi", "").replace("https://doi.org/", ""),
            "year": work.get("publication_year"),
            "venue": (work.get("primary_location", {}) or {}).get("source", {}).get("display_name"),
            "citation_count": work.get("cited_by_count"),
            "abstract": work.get("abstract", ""),
            "open_access_url": (work.get("open_access", {}) or {}).get("oa_url"),
        }


class _CrossrefProvider:
    """Fetch metadata from Crossref (free, polite pool with mailto)."""

    BASE = "https://api.crossref.org/works"

    def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        data = _api_get(f"{self.BASE}/{doi}")
        if not data or "message" not in data:
            return None
        return self._normalize(data["message"])

    @staticmethod
    def _normalize(msg: dict) -> Dict[str, Any]:
        authors = []
        for a in msg.get("author", []):
            parts = [a.get("given", ""), a.get("family", "")]
            name = " ".join(p for p in parts if p).strip()
            if name:
                authors.append(name)

        title_list = msg.get("title", [])
        title = title_list[0] if title_list else ""

        abstract = msg.get("abstract", "")
        # Crossref abstracts often have JATS XML fragments — strip tags
        if abstract and "<" in abstract:
            import re
            abstract = re.sub(r"<[^>]+>", " ", abstract)
            abstract = re.sub(r"\s+", " ", abstract).strip()

        # Year from published-print or published-online
        year = None
        for date_key in ("published-print", "published-online", "created"):
            parts = msg.get(date_key, {}).get("date-parts", [[]])
            if parts and parts[0]:
                year = parts[0][0]
                break

        venue_list = msg.get("container-title", [])
        venue = venue_list[0] if venue_list else None

        return {
            "title": title,
            "authors": authors,
            "doi": msg.get("DOI", ""),
            "year": year,
            "venue": venue,
            "citation_count": msg.get("is-referenced-by-count"),
            "abstract": abstract,
        }


class _SemanticScholarProvider:
    """Fetch metadata from Semantic Scholar (free tier, 100 req/5 min)."""

    BASE = "https://api.semanticscholar.org/graph/v1/paper"
    FIELDS = "title,authors,abstract,year,venue,citationCount,externalIds,references"

    def fetch(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """paper_id can be: DOI:..., ArXiv:..., PMCID:..., or S2 paper ID."""
        data = _api_get(f"{self.BASE}/{paper_id}", params={"fields": self.FIELDS})
        if not data:
            return None
        return self._normalize(data)

    @staticmethod
    def _normalize(paper: dict) -> Dict[str, Any]:
        authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]

        refs: List[Dict[str, str]] = []
        for ref in paper.get("references", []):
            title = ref.get("title")
            if title:
                refs.append({"title": title})

        ext_ids = paper.get("externalIds", {}) or {}

        return {
            "title": paper.get("title", ""),
            "authors": authors,
            "doi": ext_ids.get("DOI", ""),
            "arxiv_id": ext_ids.get("ArXiv", ""),
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "citation_count": paper.get("citationCount"),
            "abstract": paper.get("abstract", ""),
            "references": refs,
        }


# --------------------------------------------------------------------------- #
# Enrichment orchestrator
# --------------------------------------------------------------------------- #

class MetadataEnricher:
    """Merge metadata from multiple academic APIs into a ResearchDocument.

    Priority: Semantic Scholar > OpenAlex > Crossref.
    Missing fields in the document are filled; existing fields are NOT overwritten.
    """

    def __init__(self) -> None:
        self._openalex = _OpenAlexProvider()
        self._crossref = _CrossrefProvider()
        self._s2 = _SemanticScholarProvider()

    def enrich(self, doc: ResearchDocument) -> ResearchDocument:
        """Enrich the document in-place with metadata from APIs.
        Returns the same document (mutated) for chaining convenience.
        """
        merged: Dict[str, Any] = {}

        # Try Semantic Scholar first (richest data)
        s2_id = self._build_s2_id(doc)
        if s2_id:
            s2_data = self._s2.fetch(s2_id)
            if s2_data:
                self._merge_into(merged, s2_data)

        # OpenAlex via DOI or title
        doi = doc.doi or merged.get("doi")
        if doi:
            oa_data = self._openalex.fetch_by_doi(doi)
        elif doc.title:
            oa_data = self._openalex.fetch_by_title(doc.title)
        else:
            oa_data = None
        if oa_data:
            self._merge_into(merged, oa_data)

        # Crossref via DOI only
        doi = doi or merged.get("doi")
        if doi:
            cr_data = self._crossref.fetch_by_doi(doi)
            if cr_data:
                self._merge_into(merged, cr_data)

        # Apply merged metadata to document (only fill empty fields)
        self._apply_to_document(doc, merged)
        return doc

    @staticmethod
    def _build_s2_id(doc: ResearchDocument) -> Optional[str]:
        """Build a Semantic Scholar paper identifier."""
        arxiv_id = doc.arxiv_id
        if arxiv_id:
            return f"ArXiv:{arxiv_id}"
        doi = doc.doi
        if doi:
            return f"DOI:{doi}"
        pmc_id = doc.metadata.get("pmc_id")
        if pmc_id:
            return f"PMCID:{pmc_id}"
        return None

    @staticmethod
    def _merge_into(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Merge source into target without overwriting existing non-empty values."""
        for key, val in source.items():
            if val and not target.get(key):
                target[key] = val

    @staticmethod
    def _apply_to_document(doc: ResearchDocument, meta: Dict[str, Any]) -> None:
        """Apply enriched metadata to document fields."""
        if not doc.title and meta.get("title"):
            doc.title = meta["title"]

        if not doc.authors and meta.get("authors"):
            doc.authors = meta["authors"]

        if not doc.abstract and meta.get("abstract"):
            doc.abstract = meta["abstract"]

        # Always store enriched metadata
        if meta.get("doi") and "doi" not in doc.metadata:
            doc.metadata["doi"] = meta["doi"]
        if meta.get("arxiv_id") and "arxiv_id" not in doc.metadata:
            doc.metadata["arxiv_id"] = meta["arxiv_id"]
        if meta.get("year") and "year" not in doc.metadata:
            doc.metadata["year"] = meta["year"]
        if meta.get("venue") and "venue" not in doc.metadata:
            doc.metadata["venue"] = meta["venue"]
        if meta.get("citation_count") is not None and "citation_count" not in doc.metadata:
            doc.metadata["citation_count"] = meta["citation_count"]
        if meta.get("open_access_url") and "open_access_url" not in doc.metadata:
            doc.metadata["open_access_url"] = meta["open_access_url"]

        # Enrich references from S2 if document has none
        if not doc.references and meta.get("references"):
            doc.references = [
                Reference(raw=r.get("title", ""), title=r.get("title"))
                for r in meta["references"]
                if r.get("title")
            ]

        logger.info(
            "Enriched %s: doi=%s, year=%s, venue=%s, citations=%s, refs=%d",
            doc.id,
            doc.metadata.get("doi"),
            doc.metadata.get("year"),
            doc.metadata.get("venue"),
            doc.metadata.get("citation_count"),
            len(doc.references),
        )
