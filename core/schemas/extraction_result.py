"""Multimodal extraction result schemas."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from core.schemas.evidence import EvidenceProvenance


class ArtifactType(str, Enum):
    """Artifact type extracted from a paper."""

    TABLE = "table"
    FIGURE = "figure"
    METRIC = "metric"


class ExtractionResult(BaseModel):
    """Structured multimodal extraction result."""

    result_id: str = Field(..., description="Extraction result identifier", min_length=1)
    paper_id: str = Field(..., description="Source paper identifier", min_length=1)
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    artifact_type: ArtifactType = Field(..., description="Type of extracted artifact")
    raw_content: Any = Field(..., description="Raw extracted artifact content")
    normalized_data: Dict[str, Any] = Field(default_factory=dict, description="Normalized structured data")
    caption: Optional[str] = Field(None, description="Artifact caption if available")
    provenance: EvidenceProvenance = Field(..., description="Extraction provenance metadata")

    @field_validator("result_id", "paper_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required identifiers must be non-empty")
        return v

    @field_validator("caption")
    @classmethod
    def validate_caption(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("caption must be non-empty when provided")
        return v