"""Critique schema for adversarial hypothesis review."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from core.schemas.claim import ClaimEvidence


class CritiqueSeverity(str, Enum):
    """Severity assigned to a critique."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Critique(BaseModel):
    """Structured critique linked to a hypothesis."""

    critique_id: str = Field(..., description="Critique identifier", min_length=1)
    hypothesis_id: str = Field(..., description="Target hypothesis identifier", min_length=1)
    counter_evidence: List[ClaimEvidence] = Field(default_factory=list, description="Counter-evidence items")
    weak_assumptions: List[str] = Field(default_factory=list, description="Assumptions judged weak")
    suggested_revisions: List[str] = Field(default_factory=list, description="Concrete revision suggestions")
    severity: CritiqueSeverity = Field(..., description="Critique severity")
    confidence_rationale: Optional[str] = Field(
        None,
        description="Rationale explaining the confidence level of this critique",
    )

    @field_validator("critique_id", "hypothesis_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required identifiers must be non-empty")
        return v

    @field_validator("weak_assumptions", "suggested_revisions")
    @classmethod
    def validate_items(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("List items must be non-empty strings")
        return v