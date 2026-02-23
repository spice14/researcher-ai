"""
Claim Schema.

Defines structured representations for atomic, evidence-bound claims
extracted from research papers.

Claims must be atomic. Compound claims must be decomposed.
Conditions must be explicit when present.

CRITICAL: Claims now reference ExperimentalContext.
Two claims can only contradict if they share comparable contexts.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ClaimType(str, Enum):
    """Ontological type of a scientific claim.

    PERFORMANCE: numeric metric on dataset (BLEU, accuracy, F1)
    EFFICIENCY: compute, training time, memory, cost
    STRUCTURAL: architecture or mechanism description (non-numeric)
    """

    PERFORMANCE = "performance"
    EFFICIENCY = "efficiency"
    STRUCTURAL = "structural"


class ClaimSubtype(str, Enum):
    """Value semantics for numeric claims.

    ABSOLUTE: A direct measurement (e.g., "28.4 BLEU")
    DELTA: A relative improvement or difference (e.g., "by 2.0 BLEU")

    CRITICAL: Delta claims must NOT be aggregated with absolute values
    in belief state value-range computation. Mixing deltas with absolutes
    produces meaningless ranges (e.g., BLEU 2.0 – 41.8).
    """

    ABSOLUTE = "absolute"
    DELTA = "delta"


class Polarity(str, Enum):
    """Polarity of claim relative to a hypothesis or question."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class ConfidenceLevel(str, Enum):
    """Qualitative confidence level for claims.
    
    Derived from evidence count, source diversity, and retrieval scores.
    Numeric probabilities are prohibited unless calibrated.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimEvidence(BaseModel):
    """
    Evidence supporting or refuting a claim.

    All claims must be evidence-bound with explicit provenance.
    """

    source_id: str = Field(..., description="Document identifier (DOI, arXiv ID, etc.)", min_length=1)
    page: int = Field(..., ge=1, description="Page number where evidence appears (1-indexed)")
    snippet: str = Field(
        ...,
        description="Exact text snippet supporting the claim",
        min_length=1,
        max_length=2000,
    )
    retrieval_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Retrieval relevance score (0.0 to 1.0)",
    )

    @field_validator("source_id", "snippet")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure text fields are non-empty after stripping."""
        if len(v.strip()) == 0:
            raise ValueError("Text fields must be non-empty")
        return v


class ClaimConditions(BaseModel):
    """
    Experimental or contextual conditions under which a claim holds.

    Conditions must be explicit when present to enable proper
    contradiction detection and consensus analysis.
    """

    dataset: Optional[str] = Field(None, description="Dataset used for evaluation")
    sample_size: Optional[int] = Field(None, ge=1, description="Sample size if applicable")
    domain: Optional[str] = Field(None, description="Domain or field of application")
    experimental_setting: Optional[str] = Field(
        None,
        description="Experimental setup or methodology",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Additional constraints or boundary conditions",
    )

    @field_validator("constraints")
    @classmethod
    def validate_constraints(cls, v: List[str]) -> List[str]:
        """Ensure constraints are non-empty strings."""
        for constraint in v:
            if len(constraint.strip()) == 0:
                raise ValueError("Constraints must be non-empty strings")
        return v


class Claim(BaseModel):
    """
    Atomic claim extracted from research literature.

    Claims represent the fundamental unit of scientific assertion in the system.
    They must be:
    - Atomic (not compound)
    - Evidence-bound (with explicit provenance)
    - Context-bound (references an experimental context)
    - Condition-explicit (when applicable)

    Constraints:
    - claim_id must be unique within a session
    - Claims must be atomic; compound claims must be decomposed
    - Must have at least one piece of supporting evidence
    - Subject, predicate, and object must form a coherent statement
    - context_id must reference a valid ExperimentalContext
    
    CRITICAL INSIGHT:
    Claims are not just statements - they are observations within experimental worlds.
    Two claims can only contradict if they reference comparable contexts.
    """

    claim_id: str = Field(..., description="Unique identifier for this claim", min_length=1)
    
    # Experimental context reference (THE MISSING PRIMITIVE)
    context_id: Optional[str] = Field(
        None,
        description="Reference to ExperimentalContext defining the experimental world. "
                    "Claims without context_id cannot participate in contradiction detection "
                    "or consensus analysis."
    )
    
    subject: str = Field(
        ...,
        description="Subject of the claim (e.g., 'BERT model')",
        min_length=1,
        max_length=500,
    )
    predicate: str = Field(
        ...,
        description="Predicate or relationship (e.g., 'achieves', 'outperforms')",
        min_length=1,
        max_length=200,
    )
    object: str = Field(
        ...,
        description="Object of the claim (e.g., '92% accuracy on GLUE')",
        min_length=1,
        max_length=500,
    )
    conditions: ClaimConditions = Field(
        default_factory=ClaimConditions,
        description="Legacy experimental conditions (DEPRECATED - use context_id instead)",
    )
    evidence: List[ClaimEvidence] = Field(
        ...,
        min_length=1,
        description="Supporting evidence with provenance",
    )
    claim_type: ClaimType = Field(
        default=ClaimType.PERFORMANCE,
        description="Ontological claim type: performance, efficiency, or structural",
    )
    claim_subtype: ClaimSubtype = Field(
        default=ClaimSubtype.ABSOLUTE,
        description="Value semantics: absolute measurement or delta improvement. "
                    "Delta claims must not be aggregated with absolute values.",
    )
    polarity: Polarity = Field(..., description="Polarity: supports, refutes, or neutral")
    confidence_level: ConfidenceLevel = Field(..., description="Qualitative confidence: low, medium, high")

    @field_validator("claim_id", "subject", "predicate", "object")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure required text fields are non-empty after stripping."""
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @model_validator(mode="after")
    def validate_claim_coherence(self) -> "Claim":
        """Validate that subject-predicate-object forms a coherent statement."""
        # Basic check: ensure components don't contain only whitespace
        if not (self.subject.strip() and self.predicate.strip() and self.object.strip()):
            raise ValueError("Subject, predicate, and object must all be meaningful strings")
        return self

    def to_statement(self) -> str:
        """Convert claim to natural language statement."""
        return f"{self.subject} {self.predicate} {self.object}"
