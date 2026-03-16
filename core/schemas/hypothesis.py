"""
Hypothesis Schema.

Defines structured representations for research hypotheses generated
and refined through adversarial critique.

No hypothesis without assumptions.
Boundary conditions are mandatory when applicable.
Revision history must persist across critique cycles.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from core.schemas.claim import Claim, ConfidenceLevel


class HypothesisRevision(BaseModel):
    """
    Revision record tracking changes to a hypothesis across critique iterations.

    Maintains full provenance of hypothesis evolution.
    """

    iteration: int = Field(..., ge=1, description="Iteration number (1-indexed)")
    changes: str = Field(..., description="Description of changes made", min_length=1)
    rationale: str = Field(..., description="Rationale for the changes", min_length=1)

    @field_validator("changes", "rationale")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure revision details are non-empty."""
        if len(v.strip()) == 0:
            raise ValueError("Revision fields must be non-empty")
        return v


class Hypothesis(BaseModel):
    """
    Research hypothesis with explicit assumptions, variables, and evidence linkage.

    Hypotheses represent testable, literature-grounded research propositions
    that emerge from or are validated against existing evidence.

    Constraints:
    - hypothesis_id must be unique within a session
    - Must explicitly declare assumptions (cannot be empty)
    - Independent and dependent variables must be declared
    - Must track supporting and contradicting claims
    - Revision history must be maintained across critique cycles
    - Boundary conditions required when applicable

    Design Intent:
    Hypotheses are not free-form speculation. They are structured artifacts
    that link:
    - What is being proposed (statement)
    - What must be true for it to hold (assumptions)
    - What varies (variables)
    - Where it applies (boundary conditions)
    - What evidence exists (supporting/contradicting claims)
    - How it evolved (revision history)
    """

    hypothesis_id: str = Field(..., description="Unique identifier for this hypothesis", min_length=1)
    statement: str = Field(
        ...,
        description="The hypothesis statement (testable proposition)",
        min_length=1,
        max_length=1000,
    )
    rationale: Optional[str] = Field(
        None,
        description="Optional explicit rationale for Phase 1 compatibility",
    )
    assumptions: List[str] = Field(
        ...,
        min_length=1,
        description="Explicit assumptions underlying the hypothesis",
    )
    independent_variables: List[str] = Field(
        ...,
        min_length=1,
        description="Variables that will be manipulated or controlled",
    )
    dependent_variables: List[str] = Field(
        ...,
        min_length=1,
        description="Variables that will be measured or observed",
    )
    boundary_conditions: List[str] = Field(
        default_factory=list,
        description="Conditions defining where hypothesis applies",
    )
    supporting_claims: List[Claim] = Field(
        default_factory=list,
        description="Claims from literature that support this hypothesis",
    )
    contradicting_claims: List[Claim] = Field(
        default_factory=list,
        description="Claims from literature that contradict this hypothesis",
    )
    supporting_citations: List[str] = Field(
        default_factory=list,
        description="Citation identifiers supporting the hypothesis",
    )
    known_risks: List[str] = Field(
        default_factory=list,
        description="Known risks or failure modes associated with the hypothesis",
    )
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional numeric confidence score for compatibility with Phase 1 contract",
    )
    grounding_claim_ids: List[str] = Field(
        default_factory=list,
        description="Claim identifiers grounding this hypothesis",
    )
    iteration_number: int = Field(
        1,
        ge=1,
        description="Current revision iteration number",
    )
    novelty_basis: str = Field(
        ...,
        description="Explanation of what makes this hypothesis novel",
        min_length=1,
    )
    revision_history: List[HypothesisRevision] = Field(
        default_factory=list,
        description="History of revisions through critique cycles",
    )
    qualitative_confidence: ConfidenceLevel = Field(
        ...,
        description="Qualitative confidence assessment: low, medium, high",
    )

    @field_validator("hypothesis_id", "statement", "novelty_basis")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure required text fields are non-empty."""
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @field_validator("assumptions", "independent_variables", "dependent_variables")
    @classmethod
    def validate_non_empty_lists(cls, v: List[str]) -> List[str]:
        """Ensure required list fields contain non-empty strings."""
        if not v:
            raise ValueError("Required list fields cannot be empty")
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("List items must be non-empty strings")
        return v

    @field_validator("boundary_conditions")
    @classmethod
    def validate_boundary_conditions(cls, v: List[str]) -> List[str]:
        """Ensure boundary conditions are non-empty strings if present."""
        for condition in v:
            if len(condition.strip()) == 0:
                raise ValueError("Boundary conditions must be non-empty strings")
        return v

    @model_validator(mode="after")
    def validate_revision_history_order(self) -> "Hypothesis":
        """Validate that revision history iterations are sequential."""
        if self.revision_history:
            iterations = [rev.iteration for rev in self.revision_history]
            expected = list(range(1, len(iterations) + 1))
            if iterations != expected:
                raise ValueError(
                    f"Revision history iterations must be sequential starting from 1. "
                    f"Got {iterations}, expected {expected}"
                )
                if self.rationale is not None and len(self.rationale.strip()) == 0:
                    raise ValueError("rationale must be non-empty when provided")
        return self

    def add_revision(self, changes: str, rationale: str) -> None:
        """
        Add a new revision to the hypothesis.

        Args:
            changes: Description of what changed
            rationale: Explanation of why the change was made
        """
        next_iteration = len(self.revision_history) + 1
        revision = HypothesisRevision(
            iteration=next_iteration,
            changes=changes,
            rationale=rationale,
        )
        self.revision_history.append(revision)

    def get_evidence_balance(self) -> dict:
        """
        Calculate the balance of supporting vs contradicting evidence.

        Returns:
            Dictionary with counts and balance metrics
        """
        supporting_count = len(self.supporting_claims)
        contradicting_count = len(self.contradicting_claims)
        total = supporting_count + contradicting_count

        return {
            "supporting_count": supporting_count,
            "contradicting_count": contradicting_count,
            "total_evidence": total,
            "support_ratio": supporting_count / total if total > 0 else 0.0,
        }
