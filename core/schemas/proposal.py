"""Proposal schema for research artifact generation."""

from typing import List

from pydantic import BaseModel, Field, field_validator


class Proposal(BaseModel):
    """Structured research proposal artifact."""

    proposal_id: str = Field(..., description="Proposal identifier", min_length=1)
    hypothesis_id: str = Field(..., description="Source hypothesis identifier", min_length=1)
    novelty_statement: str = Field(..., description="Explicit novelty articulation", min_length=1)
    motivation: str = Field(..., description="Problem motivation", min_length=1)
    methodology_outline: str = Field(..., description="Methodology outline", min_length=1)
    expected_outcomes: str = Field(..., description="Expected outcomes", min_length=1)
    references: List[str] = Field(default_factory=list, description="Ordered reference identifiers or citations")

    @field_validator(
        "proposal_id",
        "hypothesis_id",
        "novelty_statement",
        "motivation",
        "methodology_outline",
        "expected_outcomes",
    )
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("References must be non-empty strings")
        return v