"""Deterministic contradiction and consensus engine (Step 4).

Purpose:
- Compare normalized claims within identical ExperimentalContext identity.
- Emit contradictions, conditional divergences, and consensus groups.

Inputs/Outputs:
- Input: AnalysisRequest
- Output: AnalysisResult

Schema References:
- services.contradiction.schemas
- services.normalization.schemas

Failure Modes:
- Missing context_id produces conditional divergence only
- Unsupported unit uses default tolerance

Testing Strategy:
- Context identity matching
- Polarity opposition contradictions
- Value divergence contradictions
- Consensus grouping with density
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from core.schemas.claim import Polarity
from services.contradiction.schemas import (
    AnalysisRequest,
    AnalysisResult,
    ComparisonKey,
    ConditionalDivergence,
    ConsensusGroup,
    ContradictionReason,
    ContradictionRecord,
)

_DEFAULT_TOLERANCE = 0.05  # 5% tolerance for ratio metrics (e.g., accuracy)


def _tolerance_for_unit(unit: str | None, overrides: Dict[str, float]) -> float:
    if unit and unit in overrides:
        return overrides[unit]
    return _DEFAULT_TOLERANCE


def _pairwise(items: List[int]) -> Iterable[Tuple[int, int]]:
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            yield items[i], items[j]


def _make_key(claim) -> ComparisonKey:
    return ComparisonKey(
        context_id=claim.context_id,
        subject=claim.subject.lower(),
        predicate=claim.predicate.lower(),
        metric_canonical=claim.metric_canonical,
    )


class ContradictionEngine:
    """Deterministic contradiction and consensus engine."""

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        contradictions: List[ContradictionRecord] = []
        conditional_divergences: List[ConditionalDivergence] = []
        consensus: List[ConsensusGroup] = []

        # Group by (context_id, metric) for contradiction detection
        # This matches the BeliefEngine grouping logic
        groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        for idx, claim in enumerate(request.claims):
            key = (claim.context_id, claim.metric_canonical)
            groups[key].append(idx)

        # Conditional divergence for same subject/predicate/metric but different contexts
        context_groups: Dict[Tuple[str, str, str], List[int]] = defaultdict(list)
        for idx, claim in enumerate(request.claims):
            key = (claim.subject.lower(), claim.predicate.lower(), claim.metric_canonical)
            context_groups[key].append(idx)

        for key, indices in context_groups.items():
            if len(indices) < 2:
                continue
            for i, j in _pairwise(indices):
                a = request.claims[i]
                b = request.claims[j]
                if a.context_id != b.context_id:
                    conditional_divergences.append(
                        ConditionalDivergence(claim_id_a=a.claim_id, claim_id_b=b.claim_id)
                    )

        for key, indices in groups.items():
            if len(indices) < 2:
                continue

            values = [request.claims[i].value_normalized for i in indices]
            unit = request.claims[indices[0]].unit_normalized
            tol = _tolerance_for_unit(unit, request.value_tolerance_by_unit)

            pair_count = 0
            contradiction_count = 0

            for i, j in _pairwise(indices):
                pair_count += 1
                a = request.claims[i]
                b = request.claims[j]
                if a.context_id != b.context_id:
                    continue

                if a.metric_canonical != b.metric_canonical:
                    continue

                # Polarity opposition is a direct contradiction
                if a.polarity != b.polarity:
                    contradictions.append(
                        ContradictionRecord(
                            claim_id_a=a.claim_id,
                            claim_id_b=b.claim_id,
                            reason=ContradictionReason(reason="polarity_opposition"),
                            value_diff=abs(a.value_normalized - b.value_normalized),
                            unit=unit,
                        )
                    )
                    contradiction_count += 1
                    continue

                # Divergence in numeric values beyond tolerance
                if abs(a.value_normalized - b.value_normalized) > tol:
                    contradictions.append(
                        ContradictionRecord(
                            claim_id_a=a.claim_id,
                            claim_id_b=b.claim_id,
                            reason=ContradictionReason(reason="value_divergence"),
                            value_diff=abs(a.value_normalized - b.value_normalized),
                            unit=unit,
                        )
                    )
                    contradiction_count += 1

            if pair_count == 0:
                continue

            value_mean = sum(values) / float(len(values))
            consensus.append(
                ConsensusGroup(
                    key=f"{key[0]}:{key[1]}",  # Format tuple as "context_id:metric"
                    claim_ids=[request.claims[i].claim_id for i in indices],
                    metric_canonical=request.claims[indices[0]].metric_canonical,
                    unit=unit,
                    value_mean=value_mean,
                    value_min=min(values),
                    value_max=max(values),
                    contradiction_density=contradiction_count / float(pair_count),
                )
            )

        return AnalysisResult(
            contradictions=contradictions,
            conditional_divergences=conditional_divergences,
            consensus=consensus,
        )
