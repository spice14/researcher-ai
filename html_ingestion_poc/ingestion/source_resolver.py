"""Source resolver — determine where a paper should be fetched from.

Resolution order (prefer structured sources over PDF):
  1. arXiv  →  html_url = arxiv.org/html/{id}
  2. PubMed Central  →  html_url = ncbi.nlm.nih.gov/pmc/articles/{id}/
  3. ACL Anthology  →  html_url = aclanthology.org/{id}/
  4. Semantic Scholar  →  metadata API
  5. DOI  →  publisher landing page via doi.org redirect

Input:  DOI, arXiv ID, paper URL, or free-form identifier
Output: ResolvedSource with source_type, html_url, pdf_url, metadata API URLs
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Identifier types
# --------------------------------------------------------------------------- #

class IdentifierType(str, Enum):
    ARXIV = "arxiv"
    PMC = "pmc"
    ACL = "acl"
    DOI = "doi"
    URL = "url"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Resolved source
# --------------------------------------------------------------------------- #

@dataclass
class ResolvedSource:
    """Where and how to fetch a paper's content."""
    identifier: str
    identifier_type: IdentifierType = IdentifierType.UNKNOWN
    html_url: Optional[str] = None
    pdf_url: Optional[str] = None
    api_urls: List[str] = field(default_factory=list)
    landing_url: Optional[str] = None


# --------------------------------------------------------------------------- #
# Regex patterns
# --------------------------------------------------------------------------- #

# arXiv: 1706.03762 or 1706.03762v3 or 2302.13971
_ARXIV_ID_RE = re.compile(r"(?:^|arxiv[.:/]*)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
# arXiv URL: https://arxiv.org/abs/1706.03762
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|html|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

# PubMed Central: PMC1234567
_PMC_RE = re.compile(r"(PMC\d{5,9})", re.IGNORECASE)

# ACL Anthology: 2023.acl-long.100 or P19-1001 or aclanthology.org/…
_ACL_ID_RE = re.compile(r"(\d{4}\.(?:acl|emnlp|naacl|eacl|findings|tacl|cl)-[a-z]+\.\d+)", re.IGNORECASE)
_ACL_URL_RE = re.compile(r"aclanthology\.org/([A-Za-z0-9._-]+)/?", re.IGNORECASE)

# DOI: 10.1234/something
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s]+)")

# Generic URL
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #

class SourceResolver:
    """Determine the best ingestion source for a paper identifier."""

    def resolve(self, identifier: str) -> ResolvedSource:
        """Resolve an identifier to structured source URLs.

        Tries each pattern in priority order and returns on first match.
        """
        identifier = identifier.strip()

        # 1. arXiv
        source = self._try_arxiv(identifier)
        if source:
            return source

        # 2. PubMed Central
        source = self._try_pmc(identifier)
        if source:
            return source

        # 3. ACL Anthology
        source = self._try_acl(identifier)
        if source:
            return source

        # 4. Generic URL (unless this is explicitly a DOI resolver URL)
        # This prevents URLs that contain DOI-looking substrings from being
        # mis-routed to doi.org and failing (e.g., Frontiers/medRxiv links).
        if _URL_RE.match(identifier):
            lower = identifier.lower()
            if not ("doi.org/" in lower or "dx.doi.org/" in lower):
                inferred_pdf = self._infer_pdf_url_for_generic(identifier)
                return ResolvedSource(
                    identifier=identifier,
                    identifier_type=IdentifierType.URL,
                    html_url=identifier,
                    pdf_url=inferred_pdf,
                    landing_url=identifier,
                )

        # 5. DOI (also adds Semantic Scholar / OpenAlex API URLs)
        source = self._try_doi(identifier)
        if source:
            return source

        # 6. Generic URL
        if _URL_RE.match(identifier):
            inferred_pdf = self._infer_pdf_url_for_generic(identifier)
            return ResolvedSource(
                identifier=identifier,
                identifier_type=IdentifierType.URL,
                html_url=identifier,
                pdf_url=inferred_pdf,
                landing_url=identifier,
            )

        # Unknown — return bare identifier, let downstream decide
        logger.warning("Could not resolve identifier: %s", identifier)
        return ResolvedSource(identifier=identifier, identifier_type=IdentifierType.UNKNOWN)

    # ------------------------------------------------------------------ #
    # Private matchers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _try_arxiv(identifier: str) -> Optional[ResolvedSource]:
        m = _ARXIV_URL_RE.search(identifier) or _ARXIV_ID_RE.search(identifier)
        if not m:
            return None
        arxiv_id = m.group(1)
        # Strip version suffix for HTML (html always serves latest)
        base_id = re.sub(r"v\d+$", "", arxiv_id)
        return ResolvedSource(
            identifier=arxiv_id,
            identifier_type=IdentifierType.ARXIV,
            html_url=f"https://arxiv.org/html/{base_id}",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            api_urls=[
                f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{base_id}?fields=title,authors,year,citationCount,references,abstract",
                f"https://api.openalex.org/works?filter=ids.openalex:arXiv:{base_id}",
            ],
            landing_url=f"https://arxiv.org/abs/{arxiv_id}",
        )

    @staticmethod
    def _try_pmc(identifier: str) -> Optional[ResolvedSource]:
        m = _PMC_RE.search(identifier)
        if not m:
            return None
        pmc_id = m.group(1).upper()
        return ResolvedSource(
            identifier=pmc_id,
            identifier_type=IdentifierType.PMC,
            html_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/",
            pdf_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/",
            api_urls=[
                f"https://api.semanticscholar.org/graph/v1/paper/PMCID:{pmc_id}?fields=title,authors,year,citationCount,references,abstract",
            ],
            landing_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/",
        )

    @staticmethod
    def _try_acl(identifier: str) -> Optional[ResolvedSource]:
        m = _ACL_URL_RE.search(identifier) or _ACL_ID_RE.search(identifier)
        if not m:
            return None
        acl_id = m.group(1).rstrip("/")
        return ResolvedSource(
            identifier=acl_id,
            identifier_type=IdentifierType.ACL,
            html_url=f"https://aclanthology.org/{acl_id}/",
            pdf_url=f"https://aclanthology.org/{acl_id}.pdf",
            api_urls=[
                f"https://api.semanticscholar.org/graph/v1/paper/ACL:{acl_id}?fields=title,authors,year,citationCount,references,abstract",
            ],
            landing_url=f"https://aclanthology.org/{acl_id}/",
        )

    @staticmethod
    def _try_doi(identifier: str) -> Optional[ResolvedSource]:
        m = _DOI_RE.search(identifier)
        if not m:
            return None
        doi = m.group(1).rstrip(".,;)")
        return ResolvedSource(
            identifier=doi,
            identifier_type=IdentifierType.DOI,
            html_url=f"https://doi.org/{doi}",
            landing_url=f"https://doi.org/{doi}",
            api_urls=[
                f"https://api.crossref.org/works/{doi}",
                f"https://api.openalex.org/works/doi:{doi}",
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,authors,year,citationCount,references,abstract",
            ],
        )

    @staticmethod
    def _infer_pdf_url_for_generic(url: str) -> Optional[str]:
        """Infer a direct PDF URL for known publisher URL patterns.

        Returns None when no deterministic mapping is known.
        """
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path

        # Direct PDF URL
        if path.lower().endswith(".pdf"):
            return url

        # bioRxiv / medRxiv content pages
        if "biorxiv.org" in host or "medrxiv.org" in host:
            if "/content/" in path and not path.endswith(".full.pdf"):
                return f"{url.rstrip('/')}.full.pdf"

        # Frontiers full article pages
        if "frontiersin.org" in host:
            if path.endswith("/full"):
                return url[:-4] + "pdf"

        # AAAI OJS direct download endpoints
        if "ojs.aaai.org" in host and "/article/download/" in path:
            return url

        # OpenReview forum pages
        if "openreview.net" in host:
            q = parse_qs(parsed.query)
            paper_id = q.get("id", [None])[0]
            if paper_id:
                return f"https://openreview.net/pdf?id={paper_id}"

        # PMLR paper pages
        if "proceedings.mlr.press" in host and path.endswith(".html"):
            stem = path.rsplit("/", 1)[-1].replace(".html", "")
            base = path.rsplit("/", 1)[0]
            return f"https://{host}{base}/{stem}/{stem}.pdf"

        # JMLR legacy and modern patterns
        if "jmlr.org" in host and path.endswith(".html"):
            # /papers/v7/hinton06a.html -> /papers/volume7/hinton06a/hinton06a.pdf
            m = re.search(r"/papers/v(\d+)/(\w+)\.html$", path)
            if m:
                vol, slug = m.group(1), m.group(2)
                return f"https://www.jmlr.org/papers/volume{vol}/{slug}/{slug}.pdf"

        # PLOS article pages
        if "journals.plos.org" in host and "/article" in path:
            q = parse_qs(parsed.query)
            doi = q.get("id", [None])[0]
            if doi:
                return f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable"

        return None
