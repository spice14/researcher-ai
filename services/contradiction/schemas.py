"""Schemas for contradiction and consensus analysis (Step 4)."""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator

from services.normalization.schemas import NormalizedClaim


class ContradictionReason(BaseModel):
    """Reason for a contradiction between two claims."""

    reason: str = Field(..., description="Reason label")
    detail: Optional[str] = Field(None, description="Optional detail")


class ContradictionRecord(BaseModel):
    """Pairwise contradiction record."""

    claim_id_a: str = Field(..., description="First claim ID")
    claim_id_b: str = Field(..., description="Second claim ID")
    reason: ContradictionReason = Field(..., description="Contradiction reason")
    value_diff: Optional[float] = Field(None, description="Absolute value difference")
    unit: Optional[str] = Field(None, description="Canonical unit")


class ConditionalDivergence(BaseModel):
    """Claims that differ due to context identity mismatch."""

    claim_id_a: str = Field(..., description="First claim ID")
    claim_id_b: str = Field(..., description="Second claim ID")
    reason: str = Field("context_mismatch", description="Reason label")


class ConsensusGroup(BaseModel):
    """Consensus group for comparable claims."""

    key: str = Field(..., description="Group identity key")
    claim_ids: List[str] = Field(..., description="Claim IDs in group")
    metric_canonical: str = Field(..., description="Canonical metric")
    unit: Optional[str] = Field(None, description="Canonical unit")
    value_mean: float = Field(..., description="Mean normalized value")
    value_min: float = Field(..., description="Minimum normalized value")
    value_max: float = Field(..., description="Maximum normalized value")
    contradiction_density: float = Field(..., ge=0.0, le=1.0, description="Contradictions / comparisons")


class AnalysisRequest(BaseModel):
    """Input schema for contradiction analysis."""

    claims: List[NormalizedClaim] = Field(..., description="Normalized claims for comparison")
    value_tolerance_by_unit: Dict[str, float] = Field(
        default_factory=dict,
        description="Optional per-unit tolerance overrides",
    )


class AnalysisResult(BaseModel):
    """Output schema for contradiction analysis."""

    contradictions: List[ContradictionRecord] = Field(default_factory=list)
    conditional_divergences: List[ConditionalDivergence] = Field(default_factory=list)
    consensus: List[ConsensusGroup] = Field(default_factory=list)


class ComparisonKey(BaseModel):
    """Comparable identity key used for grouping claims."""

    context_id: Optional[str]
    subject: str
    predicate: str
    metric_canonical: str

    def as_key(self) -> str:
        return f"{self.context_id or 'none'}|{self.subject}|{self.predicate}|{self.metric_canonical}"
