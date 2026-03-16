"""Consensus and contradiction report schemas."""

from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator

from core.schemas.claim import ClaimEvidence


class ContradictionPair(BaseModel):
    """Contradiction relation between two claims."""

    claim_a: str = Field(..., description="First claim identifier", min_length=1)
    claim_b: str = Field(..., description="Second claim identifier", min_length=1)
    evidence_a: List[ClaimEvidence] = Field(default_factory=list, description="Evidence supporting claim_a")
    evidence_b: List[ClaimEvidence] = Field(default_factory=list, description="Evidence supporting claim_b")

    @field_validator("claim_a", "claim_b")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Claim identifiers must be non-empty")
        return v

    @model_validator(mode="after")
    def validate_distinct_claims(self) -> "ContradictionPair":
        if self.claim_a == self.claim_b:
            raise ValueError("Contradiction pairs must compare two distinct claims")
        return self


class ContradictionReport(BaseModel):
    """Structured contradiction and consensus output."""

    report_id: str = Field(..., description="Report identifier", min_length=1)
    claim_cluster_id: str = Field(..., description="Normalized claim cluster identifier", min_length=1)
    consensus_claims: List[str] = Field(default_factory=list, description="Claim identifiers in consensus")
    contradiction_pairs: List[ContradictionPair] = Field(
        default_factory=list,
        description="Pairs of claims that conflict within a comparable context",
    )
    uncertainty_markers: List[str] = Field(
        default_factory=list,
        description="Structured uncertainty notes when evidence is incomplete",
    )

    @field_validator("report_id", "claim_cluster_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required identifiers must be non-empty")
        return v

    @field_validator("consensus_claims", "uncertainty_markers")
    @classmethod
    def validate_items(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("List items must be non-empty strings")
        return v