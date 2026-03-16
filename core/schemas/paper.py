"""Paper schema for ingested research documents."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Paper(BaseModel):
    """Structured paper metadata stored after ingestion."""

    paper_id: str = Field(..., description="Unique paper identifier", min_length=1)
    title: str = Field(..., description="Paper title", min_length=1)
    authors: List[str] = Field(default_factory=list, description="Ordered author names")
    abstract: Optional[str] = Field(None, description="Paper abstract text")
    doi: Optional[str] = Field(None, description="DOI if available")
    arxiv_id: Optional[str] = Field(None, description="arXiv identifier if available")
    pdf_path: str = Field(..., description="Path or URI to the source PDF", min_length=1)
    ingestion_timestamp: datetime = Field(..., description="When the paper was ingested")
    chunk_ids: List[str] = Field(default_factory=list, description="Chunk identifiers derived from this paper")

    @field_validator("paper_id", "title", "pdf_path")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @field_validator("authors", "chunk_ids")
    @classmethod
    def validate_non_empty_items(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("List items must be non-empty strings")
        return v