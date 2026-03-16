"""Chunk schema for retrievable text units."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ChunkType(str, Enum):
    """Allowed chunk types for retrieval and provenance."""

    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    CAPTION = "caption"
    TABLE = "table"


class Chunk(BaseModel):
    """Canonical retrieval chunk produced by ingestion."""

    chunk_id: str = Field(..., description="Unique chunk identifier", min_length=1)
    paper_id: str = Field(..., description="Parent paper identifier", min_length=1)
    text: str = Field(..., description="Chunk text", min_length=1)
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    embedding_id: str = Field(..., description="Embedding/vector identifier", min_length=1)
    chunk_type: ChunkType = Field(..., description="Chunk type")

    @field_validator("chunk_id", "paper_id", "text", "embedding_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v