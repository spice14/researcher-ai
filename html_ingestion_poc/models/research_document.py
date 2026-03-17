"""ResearchDocument — canonical representation of a paper inside ScholarOS.

All ingestion pipelines (HTML, API, PDF) must normalize output into this
single structure. Downstream consumers operate on ResearchDocument, never
on raw PDF bytes or HTML strings.

Bridge methods provide backward-compatible conversion to the existing
ExtractionResult (dataclass) and IngestionResult (Pydantic) schemas
used by the current pipeline.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class SourceType(str, Enum):
    """Where the document content was obtained."""
    ARXIV_HTML = "arxiv_html"
    PMC_HTML = "pmc_html"
    ACL_HTML = "acl_html"
    PUBLISHER_HTML = "publisher_html"
    PDF_PYMUPDF = "pdf_pymupdf"
    PDF_DOCLING = "pdf_docling"
    METADATA_ONLY = "metadata_only"


# --------------------------------------------------------------------------- #
# Sub-models
# --------------------------------------------------------------------------- #

class Section(BaseModel):
    """A logical section of the paper."""
    title: str
    level: int = Field(1, ge=1, le=6, description="Heading depth: 1=H1, 2=H2, …")
    content: str = Field("", description="Full text body of this section")
    page: Optional[int] = Field(None, description="Source page (PDF) or None (HTML)")


class Reference(BaseModel):
    """A single bibliographic reference."""
    raw: str = Field(..., description="Original reference string as extracted")
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None


class Figure(BaseModel):
    """A detected figure or image."""
    caption: Optional[str] = None
    url: Optional[str] = Field(None, description="Source URL or local path to image")
    page: Optional[int] = None


class Table(BaseModel):
    """A single extracted table."""
    markdown: str = Field("", description="Markdown representation of the table")
    caption: Optional[str] = None
    rows: int = 0
    cols: int = 0
    page: Optional[int] = None


# --------------------------------------------------------------------------- #
# ResearchDocument
# --------------------------------------------------------------------------- #

class ResearchDocument(BaseModel):
    """Canonical representation of a research paper.

    Every ingestion pipeline must produce this structure.
    Downstream agents, extractors, and evaluators consume only this.
    """

    # Identity
    id: str = Field(..., min_length=1, description="Stable paper identifier (DOI, arXiv ID, URL hash)")
    title: str = Field("", description="Paper title")
    authors: List[str] = Field(default_factory=list)
    abstract: str = Field("", description="Abstract text")

    # Structure
    sections: List[Section] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)

    # Provenance
    source_type: SourceType = SourceType.METADATA_ONLY
    source_url: Optional[str] = None
    raw_text: str = Field("", description="Full document text in reading order")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description=(
        "Flexible metadata: venue, year, citation_count, doi, arxiv_id, etc."
    ))
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    # --------------------------------------------------------------------- #
    # Computed helpers
    # --------------------------------------------------------------------- #

    @property
    def doi(self) -> Optional[str]:
        return self.metadata.get("doi")

    @property
    def arxiv_id(self) -> Optional[str]:
        return self.metadata.get("arxiv_id")

    @property
    def year(self) -> Optional[int]:
        y = self.metadata.get("year")
        return int(y) if y is not None else None

    @property
    def word_count(self) -> int:
        return len(self.raw_text.split())

    # --------------------------------------------------------------------- #
    # Bridge: → ExtractionResult (researcher_ai.ingestion.base_extractor)
    # --------------------------------------------------------------------- #

    def to_extraction_result(self):
        """Convert to the dataclass ExtractionResult used by the existing
        comparison harness and evaluation tools.

        Import is deferred to avoid hard coupling at module load time.
        """
        from researcher_ai.ingestion.base_extractor import (
            ExtractionResult,
            FigureData,
            SectionData,
            TableData,
        )

        return ExtractionResult(
            title=self.title or None,
            text=self.raw_text,
            sections=[
                SectionData(title=s.title, level=s.level, page=s.page)
                for s in self.sections
            ],
            tables=[
                TableData(
                    page=t.page or 0,
                    markdown=t.markdown,
                    rows=t.rows,
                    cols=t.cols,
                    caption=t.caption,
                )
                for t in self.tables
            ],
            figures=[
                FigureData(page=f.page or 0, caption=f.caption)
                for f in self.figures
            ],
            references=[r.raw for r in self.references],
            num_pages=self.metadata.get("num_pages", 0),
            extractor=self.source_type.value,
        )

    # --------------------------------------------------------------------- #
    # Bridge: → IngestionResult (services.ingestion.schemas)
    # --------------------------------------------------------------------- #

    def to_ingestion_result(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ):
        """Chunk the document text and produce an IngestionResult compatible
        with the existing ExtractionService / RAG pipeline.

        Uses IngestionService.ingest_text() so all telemetry extraction
        (metrics, units, context_ids) is preserved.
        """
        from services.ingestion.service import IngestionService
        from services.ingestion.schemas import IngestionRequest

        svc = IngestionService()
        req = IngestionRequest(
            source_id=self.id,
            raw_text=self.raw_text,
            source_uri=self.source_url,
            metadata={k: str(v) for k, v in self.metadata.items() if v is not None},
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return svc.ingest_text(req)

    # --------------------------------------------------------------------- #
    # Serialization
    # --------------------------------------------------------------------- #

    def to_markdown(self) -> str:
        """Render a clean Markdown representation of the paper."""
        parts: List[str] = []
        parts.append(f"# {self.title}\n")
        if self.authors:
            parts.append(f"**Authors:** {', '.join(self.authors)}\n")
        if self.abstract:
            parts.append(f"## Abstract\n\n{self.abstract}\n")

        for sec in self.sections:
            prefix = "#" * min(sec.level + 1, 6)  # H2 for level 1, etc.
            parts.append(f"{prefix} {sec.title}\n\n{sec.content}\n")

        if self.tables:
            parts.append("## Tables\n")
            for i, tbl in enumerate(self.tables, 1):
                cap = tbl.caption or f"Table {i}"
                parts.append(f"### {cap}\n\n{tbl.markdown}\n")

        if self.references:
            parts.append("## References\n")
            for i, ref in enumerate(self.references, 1):
                parts.append(f"{i}. {ref.raw}")
            parts.append("")

        return "\n".join(parts)

    # --------------------------------------------------------------------- #
    # Factory helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def make_id(identifier: str) -> str:
        """Create a stable, filesystem-safe ID from an arbitrary identifier."""
        clean = re.sub(r"[^a-zA-Z0-9._-]", "_", identifier)
        if len(clean) > 80:
            clean = clean[:60] + "_" + hashlib.sha256(identifier.encode()).hexdigest()[:16]
        return clean
