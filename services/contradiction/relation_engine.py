"""Epistemic Relation Graph Engine (Step 4.5).

Purpose:
- Build three-relation evidence graph from normalized claims
- Separate logical contradictions from performance variance
- Preserve context-dependent variation as conditional divergences

Inputs/Outputs:
- Input: AnalysisRequest (reused from old contradiction service)
- Output: EpistemicRelationGraph

Schema References:
- services.contradiction.epistemic_relations
- services.normalization.schemas

Failure Modes:
- Missing subject normalization could merge distinct entities
- Tolerance too strict flags natural variance as contradiction

Testing Strategy:
- Different subjects must NOT produce contradictions
- Same subject with divergent values MUST produce contradictions
- Cross-context claims must produce conditional divergences only
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from services.contradiction.epistemic_relations import (
    Contradiction,
    ConditionalDivergence,
    ContradictionReason,
    EpistemicRelationGraph,
    PerformanceVariance,
)
from services.contradiction.schemas import AnalysisRequest
from core.schemas.claim import ClaimSubtype

_DEFAULT_TOLERANCE = 0.05  # 5% tolerance for ratio metrics (natural ML variance)
_POLARITY_TOLERANCE = 1e-9  # Polarity negation must match the same numeric claim
_EPSILON = 1e-12  # Floating-point guard for tolerance edge comparisons


def _tolerance_for_unit(unit: str | None, overrides: Dict[str, float]) -> float:
    """Get tolerance threshold for a given unit."""
    if unit and unit in overrides:
        return overrides[unit]
    return _DEFAULT_TOLERANCE


def _pairwise(items: List[int]) -> Iterable[Tuple[int, int]]:
    """Generate all pairs from a list of indices."""
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            yield items[i], items[j]


class EpistemicRelationEngine:
    """
    Three-relation evidence graph builder.
    
    Separates:
    1. Contradictions (logical opposition, same entity)
    2. Performance variance (numeric spread, different entities)
    3. Conditional divergences (context-dependent variation)
    """

    def analyze(self, request: AnalysisRequest) -> EpistemicRelationGraph:
        """
        Build epistemic relation graph from normalized claims.
        
        Returns graph with three distinct edge types, each with
        correct epistemic semantics.
        """
        # Delta claims are relational and must not contaminate absolute relations.
        absolute_claims = [
            claim for claim in request.claims if claim.claim_subtype == ClaimSubtype.ABSOLUTE
        ]
        gated_request = AnalysisRequest(
            claims=absolute_claims,
            value_tolerance_by_unit=request.value_tolerance_by_unit,
        )

        contradictions = self._detect_contradictions(gated_request)
        performance_variance = self._detect_performance_variance(gated_request)
        conditional_divergences = self._detect_conditional_divergences(gated_request)

        return EpistemicRelationGraph(
            contradictions=contradictions,
            performance_variance=performance_variance,
            conditional_divergences=conditional_divergences,
        )

    @staticmethod
    def _polarity_opposition_contradiction(
        claim_a,
        claim_b,
        tol: float,
        unit: str | None,
        subject: str,
    ) -> Contradiction | None:
        if claim_a.polarity == claim_b.polarity:
            return None

        value_diff = abs(claim_a.value_normalized - claim_b.value_normalized)
        polarity_tol = min(tol, _POLARITY_TOLERANCE)
        if value_diff > (polarity_tol + _EPSILON):
            return None

        return Contradiction(
            claim_id_a=claim_a.claim_id,
            claim_id_b=claim_b.claim_id,
            reason=ContradictionReason(reason="polarity_opposition"),
            value_diff=value_diff,
            unit=unit,
            subject=subject,
        )

    def _detect_contradictions(self, request: AnalysisRequest) -> List[Contradiction]:
        """
        Detect true contradictions: same entity, incompatible values.
        
        Grouping key: (context_id, subject, metric)
        
        Epistemic constraint: Both claims CANNOT be simultaneously true.
        """
        contradictions: List[Contradiction] = []

        # Group by (context, subject, metric) - strict identity
        groups: Dict[Tuple[str, str, str], List[int]] = defaultdict(list)
        for idx, claim in enumerate(request.claims):
            key = (
                claim.context_id,
                claim.subject.lower(),  # normalize for matching
                claim.metric_canonical,
            )
            groups[key].append(idx)

        # Check each group for value contradictions
        for (context_id, subject, metric), indices in groups.items():
            if len(indices) < 2:
                continue

            unit = request.claims[indices[0]].unit_normalized
            tol = _tolerance_for_unit(unit, request.value_tolerance_by_unit)

            # Compare all pairs within this strict identity group
            for i, j in _pairwise(indices):
                claim_a = request.claims[i]
                claim_b = request.claims[j]

                # Check 1: Polarity opposition must match the same value (within tolerance).
                polarity_contradiction = self._polarity_opposition_contradiction(
                    claim_a,
                    claim_b,
                    tol,
                    unit,
                    subject,
                )
                if polarity_contradiction:
                    contradictions.append(polarity_contradiction)
                    continue

                # Check 2: Value divergence beyond tolerance
                value_diff = abs(claim_a.value_normalized - claim_b.value_normalized)
                if value_diff > (tol + _EPSILON):
                    contradictions.append(
                        Contradiction(
                            claim_id_a=claim_a.claim_id,
                            claim_id_b=claim_b.claim_id,
                            reason=ContradictionReason(reason="value_divergence"),
                            value_diff=value_diff,
                            unit=unit,
                            subject=subject,
                        )
                    )

        return contradictions

    def _detect_performance_variance(
        self, request: AnalysisRequest
    ) -> List[PerformanceVariance]:
        """
        Detect performance variance: different entities, same benchmark.
        
        Grouping key: (context_id, metric)
        
        Epistemic constraint: Claims CAN be simultaneously true.
        This is comparative spread, NOT contradiction.
        """
        variance_groups: List[PerformanceVariance] = []

        # Group by (context, metric) to find cross-subject comparisons
        groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        for idx, claim in enumerate(request.claims):
            key = (claim.context_id, claim.metric_canonical)
            groups[key].append(idx)

        for (context_id, metric), indices in groups.items():
            if len(indices) < 2:
                continue

            # Get unique subjects in this group
            subjects_in_group = {
                request.claims[i].subject.lower() for i in indices
            }

            # Performance variance requires >= 2 different subjects
            if len(subjects_in_group) < 2:
                continue  # Same subject → handled by contradiction detection

            # Compute variance statistics
            values = [request.claims[i].value_normalized for i in indices]
            claim_ids = [request.claims[i].claim_id for i in indices]
            subjects = list(subjects_in_group)
            unit = request.claims[indices[0]].unit_normalized

            value_min = min(values)
            value_max = max(values)
            value_mean = sum(values) / len(values)
            value_range = value_max - value_min

            variance_groups.append(
                PerformanceVariance(
                    claim_ids=claim_ids,
                    metric_canonical=metric,
                    context_id=context_id,
                    subjects=subjects,
                    value_min=value_min,
                    value_max=value_max,
                    value_mean=value_mean,
                    value_range=value_range,
                    unit=unit,
                )
            )

        return variance_groups

    def _detect_conditional_divergences(
        self, request: AnalysisRequest
    ) -> List[ConditionalDivergence]:
        """
        Detect conditional divergences: same entity, different contexts.
        
        Grouping key: (subject, metric) across contexts
        
        Epistemic constraint: Claims CAN be simultaneously true.
        Performance varies by evaluation context.
        """
        divergences: List[ConditionalDivergence] = []

        # Group by (subject, metric) to find cross-context variations
        groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        for idx, claim in enumerate(request.claims):
            key = (claim.subject.lower(), claim.metric_canonical)
            groups[key].append(idx)

        for (subject, metric), indices in groups.items():
            if len(indices) < 2:
                continue

            # Find pairs with different contexts
            for i, j in _pairwise(indices):
                claim_a = request.claims[i]
                claim_b = request.claims[j]

                if claim_a.context_id != claim_b.context_id:
                    divergences.append(
                        ConditionalDivergence(
                            claim_id_a=claim_a.claim_id,
                            claim_id_b=claim_b.claim_id,
                            context_a=claim_a.context_id,
                            context_b=claim_b.context_id,
                            subject=subject,
                            metric=metric,
                        )
                    )

        return divergences
