"""Schemas for deterministic ingestion service."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class IngestionRequest(BaseModel):
    """Input schema for ingestion."""

    source_id: str = Field(..., description="Unique identifier for the source", min_length=1)
    raw_text: str = Field(..., description="Raw text extracted upstream", min_length=1)
    source_uri: Optional[str] = Field(None, description="Optional URI or file path for provenance")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Source-level metadata")
    chunk_size: int = Field(1000, ge=200, description="Max characters per chunk")
    chunk_overlap: int = Field(100, ge=0, description="Overlapping characters between chunks")

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and v >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return v


class IngestionChunk(BaseModel):
    """Canonical chunk produced by ingestion."""

    chunk_id: str = Field(..., description="Deterministic chunk identifier")
    source_id: str = Field(..., description="Origin source identifier")
    page: int = Field(1, ge=1, description="1-indexed page number from source document")
    text: str = Field(..., description="Chunk text", min_length=1)
    start_char: int = Field(..., ge=0, description="Start offset within raw text")
    end_char: int = Field(..., ge=0, description="End offset within raw text")
    text_hash: str = Field(..., description="SHA-256 hash of chunk text")
    context_id: str = Field(..., description="Deterministic context identifier")
    numeric_strings: List[str] = Field(default_factory=list, description="Numeric strings in chunk")
    unit_strings: List[str] = Field(default_factory=list, description="Unit tokens in chunk")
    metric_names: List[str] = Field(default_factory=list, description="Metric names in chunk")


class ExtractionTelemetry(BaseModel):
    """Telemetry captured for downstream normalization design."""

    numeric_strings: List[str] = Field(default_factory=list, description="Numeric strings (with units if present)")
    unit_strings: List[str] = Field(default_factory=list, description="Unit tokens captured")
    metric_names: List[str] = Field(default_factory=list, description="Detected metric names")
    context_ids: List[str] = Field(default_factory=list, description="Detected context identifiers")


class IngestionResult(BaseModel):
    """Output schema for ingestion."""

    source_id: str = Field(..., description="Origin source identifier")
    chunks: List[IngestionChunk] = Field(..., description="Chunked text")
    telemetry: ExtractionTelemetry = Field(..., description="Extraction telemetry for normalization")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal ingestion warnings")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Echoed source metadata")
