"""
Evidence Record Schema.

Defines structured representations for extracted evidence from research papers.
All numeric values must preserve unit information where available.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class EvidenceType(str, Enum):
    """Type of evidence extracted from research papers."""

    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"


class EvidenceProvenance(BaseModel):
    """
    Provenance metadata tracking the source and extraction details.

    All extracted evidence must include explicit location and extraction metadata.
    """

    page: int = Field(..., ge=1, description="Page number in source document (1-indexed)")
    bounding_box: Optional[Dict[str, float]] = Field(
        None,
        description="Bounding box coordinates for extracted element",
    )
    extraction_model_version: str = Field(
        ...,
        description="Version of extraction model used",
        min_length=1,
    )

    @field_validator("bounding_box")
    @classmethod
    def validate_bounding_box(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """Validate bounding box has required coordinates."""
        if v is not None:
            required_keys = {"x", "y", "width", "height"}
            if not required_keys.issubset(v.keys()):
                raise ValueError(f"Bounding box must contain {required_keys}")
            for key in required_keys:
                if v[key] < 0:
                    raise ValueError(f"Bounding box {key} must be non-negative")
        return v


class EvidenceContext(BaseModel):
    """
    Context metadata for extracted evidence.

    Preserves semantic context necessary for correct interpretation.
    """

    caption: Optional[str] = Field(None, description="Caption or title of the evidence element")
    method_reference: Optional[str] = Field(
        None,
        description="Reference to methodology section if applicable",
    )
    metric_name: Optional[str] = Field(None, description="Name of metric being reported")
    units: Optional[str] = Field(None, description="Units of measurement")

    @field_validator("units")
    @classmethod
    def validate_units(cls, v: Optional[str]) -> Optional[str]:
        """Ensure units are non-empty if provided."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Units must be non-empty string if provided")
        return v


class EvidenceRecord(BaseModel):
    """
    Complete evidence record extracted from research papers.

    Evidence records form the atomic unit of provenance in the system.
    Every claim, hypothesis, or conclusion must trace back to evidence records.

    Constraints:
    - evidence_id must be unique within a session
    - All numeric values in extracted_data should preserve unit information
    - Type must be one of: text, table, figure
    """

    evidence_id: str = Field(..., description="Unique identifier for this evidence record", min_length=1)
    source_id: str = Field(
        ...,
        description="Identifier for the source document (DOI, arXiv ID, etc.)",
        min_length=1,
    )
    type: EvidenceType = Field(..., description="Type of evidence: text, table, or figure")
    extracted_data: Dict[str, Any] = Field(
        ...,
        description="Structured data extracted from the evidence element",
    )
    context: EvidenceContext = Field(..., description="Context metadata for interpretation")
    provenance: EvidenceProvenance = Field(..., description="Source location and extraction metadata")

    @field_validator("evidence_id", "source_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure IDs are non-empty after stripping whitespace."""
        if len(v.strip()) == 0:
            raise ValueError("ID fields must be non-empty")
        return v

    def model_dump_json_schema(self) -> Dict[str, Any]:
        """Generate JSON Schema representation for validation."""
        return self.model_json_schema()
