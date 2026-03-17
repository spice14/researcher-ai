"""HTML extraction pipeline — fetch and parse structured HTML sources.

Publisher-specific strategies:
  ArxivHTMLExtractor   — arxiv.org/html/ pages (LaTeXML-based)
  PMCHTMLExtractor     — ncbi.nlm.nih.gov/pmc/articles/ (JATS-based)
  ACLHTMLExtractor     — aclanthology.org paper pages
  GenericHTMLExtractor — readability heuristics for any publisher

Each strategy parses the DOM into a ResearchDocument with:
  title, authors, abstract, sections, tables, figures, references.

Rate limiting: 1 request/second.  Polite User-Agent header.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Type

import httpx
from bs4 import BeautifulSoup, Tag

from html_ingestion_poc.ingestion.source_resolver import IdentifierType, ResolvedSource
from html_ingestion_poc.models.research_document import (
    Figure,
    Reference,
    ResearchDocument,
    Section,
    SourceType,
    Table,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "ResearcherAI/0.1 (structured-source-ingestion; "
    "https://github.com/spice14/ScholarOS; research use only)"
)

_LAST_REQUEST_TS: float = 0.0
_MIN_INTERVAL: float = 1.0  # seconds between requests


def _rate_limited_get(url: str, *, timeout: float = 30.0, follow_redirects: bool = True) -> httpx.Response:
    """HTTP GET with rate limiting and polite headers."""
    global _LAST_REQUEST_TS
    elapsed = time.monotonic() - _LAST_REQUEST_TS
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    logger.info("GET %s", url)
    resp = httpx.get(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com/",
        },
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
    _LAST_REQUEST_TS = time.monotonic()
    resp.raise_for_status()
    return resp


# --------------------------------------------------------------------------- #
# Base strategy
# --------------------------------------------------------------------------- #

class _BaseHTMLStrategy:
    """Base class for publisher-specific extraction strategies."""

    source_type: SourceType = SourceType.PUBLISHER_HTML

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        raise NotImplementedError

    @staticmethod
    def _text(tag: Optional[Tag]) -> str:
        """Get clean text from a tag, or empty string."""
        if tag is None:
            return ""
        return re.sub(r"\s+", " ", tag.get_text(separator=" ", strip=True))

    @staticmethod
    def _table_to_markdown(table_tag: Tag) -> tuple[str, int, int]:
        """Convert an HTML <table> to a markdown table string.
        Returns (markdown, rows, cols).
        """
        rows_data: list[list[str]] = []
        for tr in table_tag.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            rows_data.append([re.sub(r"\s+", " ", c.get_text(strip=True)) for c in cells])

        if not rows_data:
            return "", 0, 0

        n_cols = max(len(r) for r in rows_data)
        # Pad short rows
        for r in rows_data:
            while len(r) < n_cols:
                r.append("")

        lines: list[str] = []
        # Header
        lines.append("| " + " | ".join(rows_data[0]) + " |")
        lines.append("| " + " | ".join(["---"] * n_cols) + " |")
        for row in rows_data[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines), len(rows_data), n_cols


# --------------------------------------------------------------------------- #
# arXiv HTML extractor
# --------------------------------------------------------------------------- #

class ArxivHTMLExtractor(_BaseHTMLStrategy):
    """Parse arxiv.org/html/ pages (LaTeXML-generated HTML5)."""

    source_type = SourceType.ARXIV_HTML

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        resp = _rate_limited_get(resolved.html_url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._get_title(soup)
        authors = self._get_authors(soup)
        abstract = self._get_abstract(soup)
        sections = self._get_sections(soup)
        tables = self._get_tables(soup)
        figures = self._get_figures(soup)
        references = self._get_references(soup)
        raw_text = self._build_raw_text(abstract, sections)

        return ResearchDocument(
            id=ResearchDocument.make_id(resolved.identifier),
            title=title,
            authors=authors,
            abstract=abstract,
            sections=sections,
            tables=tables,
            figures=figures,
            references=references,
            source_type=self.source_type,
            source_url=resolved.html_url,
            raw_text=raw_text,
            metadata={"arxiv_id": resolved.identifier},
        )

    def _get_title(self, soup: BeautifulSoup) -> str:
        # LaTeXML: <h1 class="ltx_title ltx_title_document">
        tag = soup.find("h1", class_="ltx_title")
        if tag:
            return self._text(tag)
        tag = soup.find("title")
        return self._text(tag).replace(" - arXiv", "").strip() if tag else ""

    def _get_authors(self, soup: BeautifulSoup) -> List[str]:
        # LaTeXML: <span class="ltx_personname">
        authors = []
        for span in soup.find_all("span", class_="ltx_personname"):
            name = self._text(span)
            if name and len(name) > 1:
                authors.append(name)
        if not authors:
            # Fallback: meta tags
            for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
                val = meta.get("content", "")
                if val:
                    authors.append(val)
        return authors

    def _get_abstract(self, soup: BeautifulSoup) -> str:
        # LaTeXML: <div class="ltx_abstract">
        div = soup.find("div", class_="ltx_abstract")
        if div:
            # Skip the "Abstract" heading itself
            p_tags = div.find_all("p")
            return " ".join(self._text(p) for p in p_tags).strip()
        return ""

    def _get_sections(self, soup: BeautifulSoup) -> List[Section]:
        sections: List[Section] = []
        for sec_tag in soup.find_all("section", class_=re.compile(r"ltx_section|ltx_subsection|ltx_subsubsection")):
            heading = sec_tag.find(re.compile(r"^h[2-6]$"))
            if not heading:
                continue
            title = self._text(heading)
            if not title:
                continue

            # Determine level from tag name and class
            level = 1
            cls = " ".join(sec_tag.get("class", []))
            if "ltx_subsubsection" in cls:
                level = 3
            elif "ltx_subsection" in cls:
                level = 2
            elif "ltx_section" in cls:
                level = 1

            # Gather paragraph text within this section (not nested sections)
            content_parts = []
            for child in sec_tag.children:
                if isinstance(child, Tag):
                    if child.name == "section":
                        continue  # Skip nested sections
                    if child.name in ("p", "div") and "ltx_abstract" not in " ".join(child.get("class", [])):
                        content_parts.append(self._text(child))
            content = " ".join(content_parts).strip()
            sections.append(Section(title=title, level=level, content=content))
        return sections

    def _get_tables(self, soup: BeautifulSoup) -> List[Table]:
        tables: List[Table] = []
        for fig_tag in soup.find_all("figure", class_="ltx_table"):
            caption_tag = fig_tag.find("figcaption")
            caption = self._text(caption_tag) if caption_tag else None
            table_tag = fig_tag.find("table")
            if table_tag:
                md, rows, cols = self._table_to_markdown(table_tag)
                tables.append(Table(markdown=md, caption=caption, rows=rows, cols=cols))
        # Also get bare <table> tags not inside ltx_table
        for table_tag in soup.find_all("table", class_="ltx_tabular"):
            # Skip if already captured via parent figure
            parent_fig = table_tag.find_parent("figure", class_="ltx_table")
            if parent_fig:
                continue
            md, rows, cols = self._table_to_markdown(table_tag)
            if rows > 1:
                tables.append(Table(markdown=md, rows=rows, cols=cols))
        return tables

    def _get_figures(self, soup: BeautifulSoup) -> List[Figure]:
        figures: List[Figure] = []
        for fig in soup.find_all("figure", class_="ltx_figure"):
            caption_tag = fig.find("figcaption")
            caption = self._text(caption_tag) if caption_tag else None
            img = fig.find("img")
            url = img.get("src") if img else None
            figures.append(Figure(caption=caption, url=url))
        return figures

    def _get_references(self, soup: BeautifulSoup) -> List[Reference]:
        refs: List[Reference] = []
        bib = soup.find("section", class_="ltx_bibliography")
        if not bib:
            bib = soup.find("ul", class_="ltx_biblist")
        if not bib:
            return refs

        for li in bib.find_all("li", class_="ltx_bibitem"):
            text = self._text(li)
            if len(text) > 10:
                refs.append(Reference(raw=text))
        return refs

    @staticmethod
    def _build_raw_text(abstract: str, sections: List[Section]) -> str:
        parts = []
        if abstract:
            parts.append(abstract)
        for sec in sections:
            parts.append(sec.title)
            if sec.content:
                parts.append(sec.content)
        return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# PubMed Central HTML extractor
# --------------------------------------------------------------------------- #

class PMCHTMLExtractor(_BaseHTMLStrategy):
    """Parse PubMed Central full-text HTML (JATS-based rendering)."""

    source_type = SourceType.PMC_HTML

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        resp = _rate_limited_get(resolved.html_url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._get_title(soup)
        authors = self._get_authors(soup)
        abstract = self._get_abstract(soup)
        sections = self._get_sections(soup)
        tables = self._get_tables(soup)
        figures = self._get_figures(soup)
        references = self._get_references(soup)
        raw_text = self._build_raw_text(abstract, sections)

        return ResearchDocument(
            id=ResearchDocument.make_id(resolved.identifier),
            title=title,
            authors=authors,
            abstract=abstract,
            sections=sections,
            tables=tables,
            figures=figures,
            references=references,
            source_type=self.source_type,
            source_url=resolved.html_url,
            raw_text=raw_text,
            metadata={"pmc_id": resolved.identifier},
        )

    def _get_title(self, soup: BeautifulSoup) -> str:
        # Try class-based selectors first
        tag = soup.find("h1", class_="content-title")
        if tag:
            return self._text(tag)
        # Meta tag
        meta = soup.find("meta", attrs={"name": "citation_title"})
        if meta and meta.get("content"):
            return meta["content"]
        # Bare <h1>
        h1 = soup.find("h1")
        return self._text(h1) if h1 else ""

    def _get_authors(self, soup: BeautifulSoup) -> List[str]:
        authors = []
        for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
            val = meta.get("content", "")
            if val:
                authors.append(val)
        if not authors:
            for a in soup.find_all("a", class_="contrib-author"):
                name = self._text(a)
                if name:
                    authors.append(name)
        return authors

    def _get_abstract(self, soup: BeautifulSoup) -> str:
        # Class-based
        div = soup.find("div", class_="abstract")
        if not div:
            div = soup.find("div", id="abstract")
        if div:
            paragraphs = div.find_all("p")
            return " ".join(self._text(p) for p in paragraphs).strip()
        # Section with "Abstract" heading (modern PMC)
        for sec in soup.find_all("section"):
            heading = sec.find(re.compile(r"^h[1-6]$"))
            if heading and "abstract" in self._text(heading).lower():
                paragraphs = sec.find_all("p")
                return " ".join(self._text(p) for p in paragraphs).strip()
        return ""

    def _get_sections(self, soup: BeautifulSoup) -> List[Section]:
        sections: List[Section] = []
        # Try div.tsec first (older PMC), then <section> (modern PMC)
        containers = soup.find_all("div", class_="tsec")
        if not containers:
            containers = soup.find_all("section")

        for sec_el in containers:
            heading = sec_el.find(re.compile(r"^h[2-6]$"))
            if not heading:
                continue
            title = self._text(heading)
            if not title or "abstract" in title.lower():
                continue

            level_str = heading.name[1] if heading.name else "2"
            level = max(1, int(level_str) - 1)  # h2→1, h3→2, etc.

            paragraphs = sec_el.find_all("p", recursive=False)
            content = " ".join(self._text(p) for p in paragraphs).strip()
            sections.append(Section(title=title, level=level, content=content))
        return sections

    def _get_tables(self, soup: BeautifulSoup) -> List[Table]:
        tables: List[Table] = []
        # div.table-wrap (older PMC) or direct <table> tags
        for wrap in soup.find_all("div", class_="table-wrap"):
            caption_tag = wrap.find("div", class_="caption") or wrap.find("caption")
            caption = self._text(caption_tag) if caption_tag else None
            table_tag = wrap.find("table")
            if table_tag:
                md, rows, cols = self._table_to_markdown(table_tag)
                tables.append(Table(markdown=md, caption=caption, rows=rows, cols=cols))
        # Also check <figure> or bare <table> with caption
        if not tables:
            for table_tag in soup.find_all("table"):
                md, rows, cols = self._table_to_markdown(table_tag)
                if rows > 1:
                    caption_tag = table_tag.find("caption")
                    caption = self._text(caption_tag) if caption_tag else None
                    tables.append(Table(markdown=md, caption=caption, rows=rows, cols=cols))
        return tables

    def _get_figures(self, soup: BeautifulSoup) -> List[Figure]:
        figures: List[Figure] = []
        for fig_wrap in soup.find_all(["div", "figure"], class_=re.compile(r"fig|figure")):
            caption_tag = fig_wrap.find(["div", "figcaption"], class_=re.compile(r"caption"))
            if not caption_tag:
                caption_tag = fig_wrap.find("figcaption")
            caption = self._text(caption_tag) if caption_tag else None
            img = fig_wrap.find("img")
            url = img.get("src") if img else None
            figures.append(Figure(caption=caption, url=url))
        return figures

    def _get_references(self, soup: BeautifulSoup) -> List[Reference]:
        refs: List[Reference] = []
        ref_list = soup.find("div", class_="ref-list") or soup.find("ul", class_="references")
        if not ref_list:
            # Modern PMC: section with "References" heading
            for sec in soup.find_all("section"):
                heading = sec.find(re.compile(r"^h[1-6]$"))
                if heading and "reference" in self._text(heading).lower():
                    ref_list = sec
                    break
        if not ref_list:
            return refs
        for li in ref_list.find_all("li"):
            text = self._text(li)
            if len(text) > 10:
                refs.append(Reference(raw=text))
        return refs

    @staticmethod
    def _build_raw_text(abstract: str, sections: List[Section]) -> str:
        parts = []
        if abstract:
            parts.append(abstract)
        for sec in sections:
            parts.append(sec.title)
            if sec.content:
                parts.append(sec.content)
        return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# ACL Anthology extractor
# --------------------------------------------------------------------------- #

class ACLHTMLExtractor(_BaseHTMLStrategy):
    """Parse ACL Anthology paper landing pages."""

    source_type = SourceType.ACL_HTML

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        resp = _rate_limited_get(resolved.html_url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._get_title(soup)
        authors = self._get_authors(soup)
        abstract = self._get_abstract(soup)

        return ResearchDocument(
            id=ResearchDocument.make_id(resolved.identifier),
            title=title,
            authors=authors,
            abstract=abstract,
            sections=[],  # ACL landing pages don't have full text
            tables=[],
            figures=[],
            references=[],
            source_type=self.source_type,
            source_url=resolved.html_url,
            raw_text=abstract,
            metadata={"acl_id": resolved.identifier},
        )

    def _get_title(self, soup: BeautifulSoup) -> str:
        tag = soup.find("h2", id="title")
        if tag:
            return self._text(tag)
        tag = soup.find("meta", attrs={"name": "citation_title"})
        return tag.get("content", "") if tag else ""

    def _get_authors(self, soup: BeautifulSoup) -> List[str]:
        authors = []
        for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
            val = meta.get("content", "")
            if val:
                authors.append(val)
        return authors

    def _get_abstract(self, soup: BeautifulSoup) -> str:
        div = soup.find("div", class_="acl-abstract")
        if div:
            return self._text(div)
        return ""


# --------------------------------------------------------------------------- #
# Generic HTML extractor
# --------------------------------------------------------------------------- #

class GenericHTMLExtractor(_BaseHTMLStrategy):
    """Fallback extractor using readability heuristics for any HTML page."""

    source_type = SourceType.PUBLISHER_HTML

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        resp = _rate_limited_get(resolved.html_url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._get_title(soup)
        authors = self._get_authors(soup)
        abstract = self._get_abstract(soup)
        sections = self._get_sections(soup)
        tables = self._get_tables(soup)
        figures = self._get_figures(soup)
        references = self._get_references(soup)
        raw_text = self._build_raw_text(abstract, sections)

        return ResearchDocument(
            id=ResearchDocument.make_id(resolved.identifier),
            title=title,
            authors=authors,
            abstract=abstract,
            sections=sections,
            tables=tables,
            figures=figures,
            references=references,
            source_type=self.source_type,
            source_url=resolved.html_url,
            raw_text=raw_text,
            metadata={},
        )

    def _get_title(self, soup: BeautifulSoup) -> str:
        for selector in [
            ("meta", {"name": "citation_title"}),
            ("meta", {"property": "og:title"}),
        ]:
            tag = soup.find(*selector)
            if tag and tag.get("content"):
                return tag["content"]
        h1 = soup.find("h1")
        return self._text(h1) if h1 else ""

    def _get_authors(self, soup: BeautifulSoup) -> List[str]:
        authors = []
        for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
            val = meta.get("content", "")
            if val:
                authors.append(val)
        return authors

    def _get_abstract(self, soup: BeautifulSoup) -> str:
        for cls in ["abstract", "Abstract", "paper-abstract"]:
            div = soup.find("div", class_=cls)
            if div:
                return self._text(div)
        div = soup.find("div", id="abstract")
        if div:
            return self._text(div)
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"]
        return ""

    def _get_sections(self, soup: BeautifulSoup) -> List[Section]:
        sections: List[Section] = []
        # Find all heading tags and capture following content
        article = soup.find("article") or soup.find("main") or soup.find("body") or soup
        for tag in article.find_all(re.compile(r"^h[1-6]$")):
            title = self._text(tag)
            if not title or len(title) < 2:
                continue
            level = int(tag.name[1])
            # Gather text from siblings until next heading
            content_parts: list[str] = []
            sibling = tag.find_next_sibling()
            while sibling and sibling.name not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                if sibling.name in ("p", "div"):
                    t = self._text(sibling)
                    if t:
                        content_parts.append(t)
                sibling = sibling.find_next_sibling()
            sections.append(Section(title=title, level=level, content=" ".join(content_parts)))
        return sections

    def _get_tables(self, soup: BeautifulSoup) -> List[Table]:
        tables: List[Table] = []
        for table_tag in soup.find_all("table"):
            md, rows, cols = self._table_to_markdown(table_tag)
            if rows > 1:
                caption_tag = table_tag.find("caption")
                caption = self._text(caption_tag) if caption_tag else None
                tables.append(Table(markdown=md, caption=caption, rows=rows, cols=cols))
        return tables

    def _get_figures(self, soup: BeautifulSoup) -> List[Figure]:
        figures: List[Figure] = []
        for fig in soup.find_all("figure"):
            caption_tag = fig.find("figcaption")
            caption = self._text(caption_tag) if caption_tag else None
            img = fig.find("img")
            url = img.get("src") if img else None
            figures.append(Figure(caption=caption, url=url))
        return figures

    def _get_references(self, soup: BeautifulSoup) -> List[Reference]:
        refs: List[Reference] = []
        # Look for a references section
        ref_heading = None
        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            if "reference" in self._text(h).lower():
                ref_heading = h
                break
        if ref_heading:
            ref_list = ref_heading.find_next("ul") or ref_heading.find_next("ol")
            if ref_list:
                for li in ref_list.find_all("li"):
                    text = self._text(li)
                    if len(text) > 10:
                        refs.append(Reference(raw=text))
        return refs

    @staticmethod
    def _build_raw_text(abstract: str, sections: List[Section]) -> str:
        parts = []
        if abstract:
            parts.append(abstract)
        for sec in sections:
            parts.append(sec.title)
            if sec.content:
                parts.append(sec.content)
        return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #

_STRATEGY_MAP: dict[IdentifierType, Type[_BaseHTMLStrategy]] = {
    IdentifierType.ARXIV: ArxivHTMLExtractor,
    IdentifierType.PMC: PMCHTMLExtractor,
    IdentifierType.ACL: ACLHTMLExtractor,
}


class HTMLExtractor:
    """Top-level HTML extractor — auto-selects strategy from ResolvedSource."""

    def __init__(self) -> None:
        self._strategies: dict[IdentifierType, _BaseHTMLStrategy] = {}

    def _get_strategy(self, id_type: IdentifierType) -> _BaseHTMLStrategy:
        if id_type not in self._strategies:
            cls = _STRATEGY_MAP.get(id_type, GenericHTMLExtractor)
            self._strategies[id_type] = cls()
        return self._strategies[id_type]

    def extract(self, resolved: ResolvedSource) -> ResearchDocument:
        """Fetch HTML and extract structured content.

        Raises httpx.HTTPStatusError on 4xx/5xx responses.
        """
        if not resolved.html_url:
            raise ValueError(f"No HTML URL for identifier: {resolved.identifier}")

        strategy = self._get_strategy(resolved.identifier_type)
        logger.info(
            "HTML extraction [%s] for %s via %s",
            strategy.__class__.__name__,
            resolved.identifier,
            resolved.html_url,
        )
        return strategy.extract(resolved)
