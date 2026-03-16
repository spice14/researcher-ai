"""Belief state schemas for deterministic epistemic reasoning."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field

from services.contradiction.epistemic_relations import Contradiction
from services.normalization.schemas import NormalizedClaim


class QualitativeConfidence(str, Enum):
    """Deterministic confidence levels based on explicit thresholds."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EpistemicStatus(str, Enum):
    """Deterministic epistemic status classification."""

    SUPPORTED = "supported"
    CONTESTED = "contested"
    WEAKLY_SUPPORTED = "weakly_supported"
    CONDITIONALLY_DIVERGENT = "conditionally_divergent"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class NormalizedValueSummary(BaseModel):
    """Statistical summary of normalized values."""

    min: float = Field(description="Minimum normalized value")
    max: float = Field(description="Maximum normalized value")
    mean: float = Field(description="Mean normalized value")


class BeliefStateTrace(BaseModel):
    """Provenance trace for belief state."""

    supporting_claim_ids: List[str] = Field(
        description="Claim IDs with SUPPORTS polarity"
    )
    refuting_claim_ids: List[str] = Field(description="Claim IDs with REFUTES polarity")


class BeliefState(BaseModel):
    """Deterministic belief state derived from normalized claims and contradictions."""

    proposition_id: str = Field(
        description="Unique identifier for this belief proposition"
    )
    context_id: str = Field(
        description="Experimental context (e.g., ctx_glue, ctx_squad)"
    )
    metric: str = Field(description="Canonical metric name (e.g., ACCURACY, F1_MACRO)")
    normalized_value_summary: NormalizedValueSummary = Field(
        description="Statistical summary of normalized values"
    )
    supporting_count: int = Field(description="Number of supporting claims")
    refuting_count: int = Field(description="Number of refuting claims")
    contradiction_density: float = Field(
        description="Ratio of refuting claims to total claims"
    )
    consensus_strength: float = Field(
        description="Difference between supporting and refuting counts"
    )
    qualitative_confidence: QualitativeConfidence = Field(
        description="Deterministic confidence level"
    )
    epistemic_status: EpistemicStatus = Field(
        description="Deterministic epistemic classification"
    )
    trace: BeliefStateTrace = Field(description="Provenance trace")


class BeliefRequest(BaseModel):
    """Request for belief state computation."""

    normalized_claims: List[NormalizedClaim] = Field(
        description="Normalized claims to analyze"
    )
    contradictions: List[Contradiction] = Field(
        default_factory=list,
        description="True contradictions (same entity, incompatible values)",
    )
