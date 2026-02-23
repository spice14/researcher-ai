"""Epistemic relation schemas for scientific evidence graphs.

This module defines the three fundamental relations between claims:

1. CONTRADICTION - logical opposition between claims about same entity
2. PERFORMANCE_VARIANCE - numeric spread across different entities
3. CONDITIONAL_DIVERGENCE - context-dependent variation

These relations form the epistemic substrate for belief calibration.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ContradictionReason(BaseModel):
    """Reason for a contradiction between two claims."""

    reason: str = Field(..., description="Reason label")
    detail: Optional[str] = Field(None, description="Optional detail")


class Contradiction(BaseModel):
    """
    Logical contradiction: Same entity, same metric, opposing values.
    
    Example:
        "BERT achieves 92% on GLUE" contradicts "BERT achieves 45% on GLUE"
    
    Identity constraints:
        - same context_id
        - same subject (normalized)
        - same metric_canonical
        - incompatible values (beyond tolerance)
    
    Epistemic semantics:
        Both claims CANNOT be simultaneously true.
        One must be false, incomplete, or context-misspecified.
    """

    claim_id_a: str = Field(..., description="First claim ID")
    claim_id_b: str = Field(..., description="Second claim ID")
    reason: ContradictionReason = Field(..., description="Contradiction reason")
    value_diff: float = Field(..., description="Absolute value difference")
    unit: Optional[str] = Field(None, description="Canonical unit")
    subject: str = Field(..., description="Subject entity (for identity verification)")


class PerformanceVariance(BaseModel):
    """
    Performance spread: Different entities, same benchmark, numeric variance.
    
    Example:
        "BERT achieves 92% on GLUE" vs "GPT achieves 45% on GLUE"
    
    Identity constraints:
        - same context_id
        - same metric_canonical
        - DIFFERENT subjects
    
    Epistemic semantics:
        Both claims CAN be simultaneously true.
        This is comparative variance, NOT logical contradiction.
        Feeds ranking, SOTA detection, distribution analysis.
    """

    claim_ids: List[str] = Field(..., description="All claim IDs in variance group")
    metric_canonical: str = Field(..., description="Shared metric")
    context_id: str = Field(..., description="Shared context")
    subjects: List[str] = Field(..., description="Different subjects being compared")
    value_min: float = Field(..., description="Minimum value in group")
    value_max: float = Field(..., description="Maximum value in group")
    value_mean: float = Field(..., description="Mean value")
    value_range: float = Field(..., description="Max - Min (performance spread)")
    unit: Optional[str] = Field(None, description="Canonical unit")


class ConditionalDivergence(BaseModel):
    """
    Context-dependent variation: Same entity, different contexts.
    
    Example:
        "BERT achieves 92% on GLUE" vs "BERT achieves 88% on SQuAD"
    
    Identity constraints:
        - DIFFERENT context_id
        - same subject
        - same metric_canonical
    
    Epistemic semantics:
        Both claims CAN be simultaneously true.
        Performance varies by evaluation context.
        Not a contradiction—a conditional fact.
    """

    claim_id_a: str = Field(..., description="First claim ID")
    claim_id_b: str = Field(..., description="Second claim ID")
    context_a: str = Field(..., description="First context")
    context_b: str = Field(..., description="Second context")
    subject: str = Field(..., description="Subject entity")
    metric: str = Field(..., description="Metric name")


class EpistemicRelationGraph(BaseModel):
    """
    Complete epistemic relation graph for a set of claims.
    
    This structure separates three distinct semantic relations:
    - contradictions: logical conflicts requiring resolution
    - performance_variance: comparative spread (co-true)
    - conditional_divergences: context-bound variation (co-true)
    
    Only contradictions should feed contradiction_density in belief calibration.
    """

    contradictions: List[Contradiction] = Field(
        default_factory=list,
        description="Logical contradictions (same entity, incompatible values)",
    )
    performance_variance: List[PerformanceVariance] = Field(
        default_factory=list,
        description="Performance spread across entities (co-true)",
    )
    conditional_divergences: List[ConditionalDivergence] = Field(
        default_factory=list,
        description="Context-dependent variation (co-true)",
    )
