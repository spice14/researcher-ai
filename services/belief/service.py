"""Deterministic belief engine with explicit calibration rules."""

import hashlib
import json
from collections import defaultdict
from typing import Dict, List, Tuple

from core.schemas.claim import ClaimSubtype, Polarity
from services.belief.schemas import (
    BeliefRequest,
    BeliefState,
    BeliefStateTrace,
    EpistemicStatus,
    NormalizedValueSummary,
    QualitativeConfidence,
)
from services.normalization.schemas import NormalizedClaim


class BeliefEngine:
    """
    Deterministic belief state engine.

    Converts normalized claims and contradiction results into structured BeliefState objects.
    All confidence thresholds are explicit constants.
    No LLM calls, no embeddings, no hidden heuristics.
    """

    # Explicit threshold constants for confidence calibration
    HIGH_CONFIDENCE_MIN_SUPPORT = 3
    HIGH_CONFIDENCE_MIN_SUPPORT_RATIO = 0.75
    HIGH_CONFIDENCE_MAX_CONTRADICTION_DENSITY = 0.2

    MEDIUM_CONFIDENCE_MIN_SUPPORT = 2
    MEDIUM_CONFIDENCE_MIN_SUPPORT_RATIO = 0.6

    SUPPORTED_MIN_SUPPORT_RATIO = 0.75
    WEAKLY_SUPPORTED_MIN_SUPPORT_RATIO = 0.4
    WEAKLY_SUPPORTED_MAX_SUPPORT_RATIO = 0.75

    def __init__(self):
        """Initialize belief engine with deterministic rules."""
        pass

    def compute_beliefs(self, request: BeliefRequest) -> List[BeliefState]:
        """
        Compute belief states from normalized claims.

        Groups claims by (context_id, metric) and computes deterministic belief state.
        Applies multi-context evidence boost: if same subject+metric appears across
        ≥2 contexts with all SUPPORTS polarity, confidence ≥ MEDIUM.

        Args:
            request: BeliefRequest with normalized claims and contradiction records

        Returns:
            List of BeliefState objects, one per unique (context_id, metric) pair
        """
        # Group claims by (context_id, metric)
        groups: Dict[Tuple[str, str], List[NormalizedClaim]] = defaultdict(list)

        for claim in request.normalized_claims:
            key = (claim.context_id, claim.metric_canonical)
            groups[key].append(claim)

        # Detect multi-context evidence: same subject+metric across ≥2 different contexts
        # with all SUPPORTS polarity → these groups get confidence boost
        boosted_keys = self._find_multi_context_boost(request.normalized_claims)

        # Compute belief state for each group
        beliefs = []
        for (context_id, metric), claims in groups.items():
            belief = self._compute_belief_for_group(
                context_id, metric, claims, request.contradictions,
                boost=(context_id, metric) in boosted_keys,
            )
            beliefs.append(belief)

        return beliefs

    def _find_multi_context_boost(
        self, claims: List[NormalizedClaim]
    ) -> set:
        """Find (context_id, metric) keys that benefit from multi-context evidence.

        Rule: if the same subject+metric appears across ≥2 different contexts,
        and all such claims have SUPPORTS polarity, then all those groups get
        a confidence boost to at least MEDIUM.
        """
        # Group by (subject, metric) to find cross-context evidence
        subject_metric_groups: Dict[Tuple[str, str], List[NormalizedClaim]] = defaultdict(list)
        for claim in claims:
            key = (claim.subject, claim.metric_canonical)
            subject_metric_groups[key].append(claim)

        boosted: set = set()
        for (subject, metric), group_claims in subject_metric_groups.items():
            contexts = {c.context_id for c in group_claims}
            if len(contexts) < 2:
                continue
            # All claims must be SUPPORTS
            if all(c.polarity == Polarity.SUPPORTS for c in group_claims):
                for c in group_claims:
                    boosted.add((c.context_id, c.metric_canonical))

        return boosted

    def _compute_belief_for_group(
        self,
        context_id: str,
        metric: str,
        claims: List[NormalizedClaim],
        contradictions: List,
        boost: bool = False,
    ) -> BeliefState:
        """
        Compute deterministic belief state for a single group.

        Args:
            context_id: Experimental context identifier
            metric: Canonical metric name
            claims: List of normalized claims for this (context_id, metric) pair
            contradictions: List of Contradiction objects (true contradictions only)

        Returns:
            BeliefState with deterministic confidence and epistemic status
        """
        # Count true contradictions involving claims in this group
        # These are contradictions where:
        # - Both claims are in this (context, metric) group
        # - Same subject (enforced by contradiction detection)
        # - Incompatible values
        
        claim_ids_in_group = {c.claim_id for c in claims}
        all_values = [c.value_normalized for c in claims]

        # Delta contamination gate: exclude delta claims from value-range
        # aggregation. Delta values (e.g., "improvement by 2.0 BLEU") must
        # not pollute absolute measurement ranges (e.g., 28.4-41.8 BLEU).
        absolute_values = [
            c.value_normalized for c in claims
            if getattr(c, "claim_subtype", ClaimSubtype.ABSOLUTE) == ClaimSubtype.ABSOLUTE
        ]
        range_values = absolute_values if absolute_values else all_values
        mean_value = sum(range_values) / len(range_values)
        
        group_contradictions = 0
        for contradiction in contradictions:
            claim_a_in_group = contradiction.claim_id_a in claim_ids_in_group
            claim_b_in_group = contradiction.claim_id_b in claim_ids_in_group
            if claim_a_in_group and claim_b_in_group:
                group_contradictions += 1
        
        # Use original polarity from claims (don't infer outliers)
        supporting = [c for c in claims if c.polarity == Polarity.SUPPORTS]
        refuting = [c for c in claims if c.polarity == Polarity.REFUTES]

        supporting_count = len(supporting)
        refuting_count = len(refuting)
        total_count = supporting_count + refuting_count

        # Compute value statistics from ABSOLUTE claims only (delta gate)
        value_summary = NormalizedValueSummary(
            min=min(range_values),
            max=max(range_values),
            mean=mean_value,
        )

        # Calculate contradiction_density based on contradiction records
        # Similar to ConsensusGroup: contradictions / total_pairs
        total_pairs = (total_count * (total_count - 1)) // 2 if total_count > 1 else 0
        contradiction_density = (
            group_contradictions / total_pairs if total_pairs > 0 else 0.0
        )
        consensus_strength = float(supporting_count - refuting_count)

        # Compute support ratio
        support_ratio = (
            supporting_count / total_count if total_count > 0 else 0.0
        )

        # Deterministic qualitative confidence
        qualitative_confidence = self._compute_confidence(
            supporting_count, support_ratio, contradiction_density
        )

        # Apply multi-context evidence boost
        if boost and qualitative_confidence == QualitativeConfidence.LOW:
            qualitative_confidence = QualitativeConfidence.MEDIUM

        # Deterministic epistemic status
        epistemic_status = self._compute_epistemic_status(
            supporting_count, refuting_count, support_ratio
        )

        # Build trace
        trace = BeliefStateTrace(
            supporting_claim_ids=[c.claim_id for c in supporting],
            refuting_claim_ids=[c.claim_id for c in refuting],
        )

        # Generate deterministic proposition_id
        proposition_payload = {
            "context_id": context_id,
            "metric": metric,
        }
        proposition_id = self._hash_payload(proposition_payload)

        return BeliefState(
            proposition_id=proposition_id,
            context_id=context_id,
            metric=metric,
            normalized_value_summary=value_summary,
            supporting_count=supporting_count,
            refuting_count=refuting_count,
            contradiction_density=contradiction_density,
            consensus_strength=consensus_strength,
            qualitative_confidence=qualitative_confidence,
            epistemic_status=epistemic_status,
            trace=trace,
        )

    def _compute_confidence(
        self, supporting_count: int, support_ratio: float, contradiction_density: float
    ) -> QualitativeConfidence:
        """
        Deterministic confidence calibration.

        Rules:
        - HIGH: supporting_count >= 3 AND support_ratio >= 0.75 AND contradiction_density <= 0.2
        - MEDIUM: supporting_count >= 2 AND support_ratio >= 0.6
        - LOW: otherwise

        Args:
            supporting_count: Number of supporting claims
            support_ratio: Ratio of supporting to total claims
            contradiction_density: Ratio of refuting to total claims

        Returns:
            QualitativeConfidence enum value
        """
        if (
            supporting_count >= self.HIGH_CONFIDENCE_MIN_SUPPORT
            and support_ratio >= self.HIGH_CONFIDENCE_MIN_SUPPORT_RATIO
            and contradiction_density <= self.HIGH_CONFIDENCE_MAX_CONTRADICTION_DENSITY
        ):
            return QualitativeConfidence.HIGH

        if (
            supporting_count >= self.MEDIUM_CONFIDENCE_MIN_SUPPORT
            and support_ratio >= self.MEDIUM_CONFIDENCE_MIN_SUPPORT_RATIO
        ):
            return QualitativeConfidence.MEDIUM

        return QualitativeConfidence.LOW

    def _compute_epistemic_status(
        self, supporting_count: int, refuting_count: int, support_ratio: float
    ) -> EpistemicStatus:
        """
        Deterministic epistemic status classification.

        Rules:
        - insufficient_evidence: no claims
        - supported: support_ratio >= 0.75 AND refuting_count == 0
        - contested: refuting_count > supporting_count
        - weakly_supported: support_ratio between 0.4 and 0.75
        - Default fallback: weakly_supported

        Args:
            supporting_count: Number of supporting claims
            refuting_count: Number of refuting claims
            support_ratio: Ratio of supporting to total claims

        Returns:
            EpistemicStatus enum value
        """
        total_count = supporting_count + refuting_count

        if total_count == 0:
            return EpistemicStatus.INSUFFICIENT_EVIDENCE

        if (
            support_ratio >= self.SUPPORTED_MIN_SUPPORT_RATIO
            and refuting_count == 0
        ):
            return EpistemicStatus.SUPPORTED

        if refuting_count > supporting_count:
            return EpistemicStatus.CONTESTED

        if (
            support_ratio >= self.WEAKLY_SUPPORTED_MIN_SUPPORT_RATIO
            and support_ratio < self.WEAKLY_SUPPORTED_MAX_SUPPORT_RATIO
        ):
            return EpistemicStatus.WEAKLY_SUPPORTED

        # Fallback for edge cases (e.g., support_ratio < 0.4)
        return EpistemicStatus.WEAKLY_SUPPORTED

    def _hash_payload(self, payload: dict) -> str:
        """Generate deterministic hash for proposition ID."""
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
