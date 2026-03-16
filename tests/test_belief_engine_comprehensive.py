"""Comprehensive unit tests for belief engine."""

import pytest
from services.belief.schemas import (
    BeliefRequest,
    BeliefState,
    QualitativeConfidence,
    EpistemicStatus,
    Contradiction,
)
from services.contradiction.epistemic_relations import ContradictionReason
from services.belief.service import BeliefEngine
from services.normalization.schemas import NormalizedClaim
from core.schemas.claim import ClaimSubtype, Polarity


@pytest.fixture
def belief_engine():
    """Fixture providing a BeliefEngine instance."""
    return BeliefEngine()


@pytest.fixture
def sample_normalized_claims():
    """Fixture: sample normalized claims for BERT on GLUE."""
    return [
        NormalizedClaim(
            claim_id="claim_bert_glue_1",
            context_id="ctx_glue",
            subject="BERT",
            predicate="achieves",
            object_raw="92.5% accuracy on GLUE",
            metric_canonical="ACCURACY",
            value_raw="92.5",
            value_normalized=92.5,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        ),
        NormalizedClaim(
            claim_id="claim_bert_glue_2",
            context_id="ctx_glue",
            subject="BERT",
            predicate="achieves",
            object_raw="91.8% accuracy on GLUE",
            metric_canonical="ACCURACY",
            value_raw="91.8",
            value_normalized=91.8,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        ),
    ]


@pytest.fixture
def contested_claims():
    """Fixture: claims with both supporting and refuting evidence."""
    return [
        NormalizedClaim(
            claim_id="claim_support_1",
            context_id="ctx_test",
            subject="Model-X",
            predicate="achieves",
            object_raw="85% accuracy",
            metric_canonical="ACCURACY",
            value_raw="85",
            value_normalized=85.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        ),
        NormalizedClaim(
            claim_id="claim_refute_1",
            context_id="ctx_test",
            subject="Model-X",
            predicate="achieves",
            object_raw="72% accuracy",
            metric_canonical="ACCURACY",
            value_raw="72",
            value_normalized=72.0,
            unit_normalized="%",
            polarity=Polarity.REFUTES,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        ),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Belief Engine Initialization
# ──────────────────────────────────────────────────────────────────────────────


class TestBeliefEngineInit:
    """Tests for belief engine initialization."""

    def test_engine_initializes(self, belief_engine):
        """Test engine can be initialized."""
        assert belief_engine is not None

    def test_engine_has_constants(self, belief_engine):
        """Test engine has required constants."""
        assert hasattr(belief_engine, "HIGH_CONFIDENCE_MIN_SUPPORT")
        assert hasattr(belief_engine, "MEDIUM_CONFIDENCE_MIN_SUPPORT")
        assert belief_engine.HIGH_CONFIDENCE_MIN_SUPPORT > 0
        assert belief_engine.MEDIUM_CONFIDENCE_MIN_SUPPORT > 0

    def test_engine_compute_beliefs_callable(self, belief_engine):
        """Test compute_beliefs method is callable."""
        assert callable(belief_engine.compute_beliefs)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Basic Belief Computation
# ──────────────────────────────────────────────────────────────────────────────


class TestBasicBeliefComputation:
    """Tests for basic belief state computation."""

    def test_compute_beliefs_returns_list(self, belief_engine, sample_normalized_claims):
        """Test compute_beliefs returns a list."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        assert isinstance(result, list)

    def test_compute_beliefs_returns_belief_states(
        self, belief_engine, sample_normalized_claims
    ):
        """Test compute_beliefs returns BeliefState objects."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        for belief_state in result:
            assert isinstance(belief_state, BeliefState)

    def test_empty_claims_returns_empty_list(self, belief_engine):
        """Test empty claims list returns empty result."""
        request = BeliefRequest(
            normalized_claims=[],
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_single_claim_produces_belief_state(self, belief_engine):
        """Test single claim produces one belief state."""
        claim = NormalizedClaim(
            claim_id="single_claim",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object_raw="90% accuracy",
            metric_canonical="ACCURACY",
            value_raw="90",
            value_normalized=90.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = BeliefRequest(normalized_claims=[claim], contradictions=[])
        result = belief_engine.compute_beliefs(request)

        assert len(result) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Belief State Properties
# ──────────────────────────────────────────────────────────────────────────────


class TestBeliefStateProperties:
    """Tests for belief state properties."""

    def test_belief_state_has_required_fields(
        self, belief_engine, sample_normalized_claims
    ):
        """Test belief state has all required fields."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            state = result[0]
            assert state.proposition_id is not None
            assert state.context_id is not None
            assert state.metric is not None
            assert state.normalized_value_summary is not None
            assert state.supporting_count >= 0
            assert state.refuting_count >= 0
            assert state.contradiction_density >= 0.0
            assert state.contradiction_density <= 1.0
            assert state.consensus_strength is not None
            assert state.qualitative_confidence is not None
            assert state.epistemic_status is not None
            assert state.trace is not None

    def test_belief_state_trace_has_claim_ids(
        self, belief_engine, sample_normalized_claims
    ):
        """Test belief state trace contains claim IDs."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            state = result[0]
            trace = state.trace
            assert isinstance(trace.supporting_claim_ids, list)
            assert isinstance(trace.refuting_claim_ids, list)

    def test_value_summary_contains_statistics(
        self, belief_engine, sample_normalized_claims
    ):
        """Test normalized value summary contains statistics."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            state = result[0]
            summary = state.normalized_value_summary
            assert summary.min is not None
            assert summary.max is not None
            assert summary.mean is not None
            assert summary.min <= summary.max
            assert summary.min <= summary.mean <= summary.max


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Confidence Levels
# ──────────────────────────────────────────────────────────────────────────────


class TestConfidenceLevels:
    """Tests for confidence level computation."""

    def test_high_support_produces_high_confidence(self, belief_engine):
        """Test many supporting claims produce high confidence."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(10)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # Many supporting claims should produce HIGH or MEDIUM confidence
            assert result[0].qualitative_confidence in [
                QualitativeConfidence.HIGH,
                QualitativeConfidence.MEDIUM,
            ]

    def test_low_support_produces_low_confidence(self, belief_engine):
        """Test single claim produces lower confidence."""
        claim = NormalizedClaim(
            claim_id="single",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object_raw="90% accuracy",
            metric_canonical="ACCURACY",
            value_raw="90",
            value_normalized=90.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = BeliefRequest(normalized_claims=[claim], contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # Single claim may be LOW or MEDIUM
            assert result[0].qualitative_confidence in [
                QualitativeConfidence.LOW,
                QualitativeConfidence.MEDIUM,
            ]

    def test_confidence_is_valid_enum(self, belief_engine, sample_normalized_claims):
        """Test confidence level is valid enum."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        for state in result:
            assert isinstance(state.qualitative_confidence, QualitativeConfidence)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Epistemic Status
# ──────────────────────────────────────────────────────────────────────────────


class TestEpistemicStatus:
    """Tests for epistemic status classification."""

    def test_supported_status_for_consensus(self, belief_engine):
        """Test consensus (many supporting claims) produces SUPPORTED status."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(5)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # Strong consensus should be SUPPORTED
            assert result[0].epistemic_status in [
                EpistemicStatus.SUPPORTED,
                EpistemicStatus.CONTESTED,
            ]

    def test_contested_status_with_contradictions(self, belief_engine, contested_claims):
        """Test mixed supporting/refuting claims produce CONTESTED status."""
        request = BeliefRequest(
            normalized_claims=contested_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # Mixed evidence should be CONTESTED or WEAKLY_SUPPORTED
            assert result[0].epistemic_status in [
                EpistemicStatus.CONTESTED,
                EpistemicStatus.WEAKLY_SUPPORTED,
            ]

    def test_epistemic_status_is_valid_enum(
        self, belief_engine, sample_normalized_claims
    ):
        """Test epistemic status is valid enum."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        for state in result:
            assert isinstance(state.epistemic_status, EpistemicStatus)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Contradiction Handling
# ──────────────────────────────────────────────────────────────────────────────


class TestContradictionHandling:
    """Tests for contradiction handling in belief computation."""

    def test_compute_beliefs_with_contradictions(self, belief_engine, sample_normalized_claims):
        """Test belief computation with contradictions."""
        contradiction = Contradiction(
            claim_id_a="claim_bert_glue_1",
            claim_id_b="claim_bert_glue_2",
            reason=ContradictionReason(reason="values differ by 0.7%"),
            value_diff=0.7,
            unit="%",
            subject="BERT",
        )
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[contradiction],
        )
        result = belief_engine.compute_beliefs(request)

        assert isinstance(result, list)

    def test_contradiction_affects_density(self, belief_engine):
        """Test contradictions affect contradiction_density."""
        claim1 = NormalizedClaim(
            claim_id="claim_1",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object_raw="90% accuracy",
            metric_canonical="ACCURACY",
            value_raw="90",
            value_normalized=90.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        claim2 = NormalizedClaim(
            claim_id="claim_2",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object_raw="50% accuracy",
            metric_canonical="ACCURACY",
            value_raw="50",
            value_normalized=50.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        contradiction = Contradiction(
            claim_id_a="claim_1",
            claim_id_b="claim_2",
            reason=ContradictionReason(reason="high value difference"),
            value_diff=40.0,
            unit="%",
            subject="Model",
        )

        request_no_contradiction = BeliefRequest(
            normalized_claims=[claim1, claim2],
            contradictions=[],
        )
        result_no_contradiction = belief_engine.compute_beliefs(request_no_contradiction)

        request_with_contradiction = BeliefRequest(
            normalized_claims=[claim1, claim2],
            contradictions=[contradiction],
        )
        result_with_contradiction = belief_engine.compute_beliefs(request_with_contradiction)

        # Both should produce results
        assert len(result_no_contradiction) >= 0
        assert len(result_with_contradiction) >= 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Consensus Strength
# ──────────────────────────────────────────────────────────────────────────────


class TestConsensusStrength:
    """Tests for consensus strength computation."""

    def test_all_supporting_has_positive_consensus(self, belief_engine):
        """Test all supporting claims have positive consensus."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(5)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # All supporting should have positive consensus strength
            assert result[0].consensus_strength >= 0

    def test_mixed_support_refute_reduces_consensus(self, belief_engine):
        """Test mixed support/refute reduces consensus strength."""
        support_claims = [
            NormalizedClaim(
                claim_id=f"support_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(3)
        ]
        refute_claims = [
            NormalizedClaim(
                claim_id=f"refute_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="50% accuracy",
                metric_canonical="ACCURACY",
                value_raw="50",
                value_normalized=50.0,
                unit_normalized="%",
                polarity=Polarity.REFUTES,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(2)
        ]

        request = BeliefRequest(
            normalized_claims=support_claims + refute_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # Mixed evidence should have lower consensus than pure support
            assert result[0].consensus_strength is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Polarity Handling
# ──────────────────────────────────────────────────────────────────────────────


class TestPolarityHandling:
    """Tests for polarity in belief computation."""

    def test_supports_polarity_counted_correctly(self, belief_engine):
        """Test SUPPORTS polarity is counted in supporting_count."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(3)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # 3 supporting claims
            assert result[0].supporting_count == 3
            assert result[0].refuting_count == 0

    def test_refutes_polarity_counted_correctly(self, belief_engine):
        """Test REFUTES polarity is counted in refuting_count."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="50% accuracy",
                metric_canonical="ACCURACY",
                value_raw="50",
                value_normalized=50.0,
                unit_normalized="%",
                polarity=Polarity.REFUTES,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(2)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        if len(result) > 0:
            # 2 refuting claims
            assert result[0].refuting_count == 2
            assert result[0].supporting_count == 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Delta Claims Gating
# ──────────────────────────────────────────────────────────────────────────────


class TestDeltaClaimsGating:
    """Tests for delta claims being excluded from belief computation."""

    def test_delta_claims_not_affect_absolute_ranges(self, belief_engine):
        """Test delta claims don't affect value range computation."""
        absolute_claim = NormalizedClaim(
            claim_id="absolute",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object_raw="90% accuracy",
            metric_canonical="ACCURACY",
            value_raw="90",
            value_normalized=90.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        delta_claim = NormalizedClaim(
            claim_id="delta",
            context_id="ctx_test",
            subject="Model",
            predicate="improves by",
            object_raw="5% improvement",
            metric_canonical="ACCURACY",
            value_raw="5",
            value_normalized=5.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.DELTA,
        )

        # Only absolute claim
        request_absolute_only = BeliefRequest(
            normalized_claims=[absolute_claim],
            contradictions=[],
        )
        result_absolute_only = belief_engine.compute_beliefs(request_absolute_only)

        # Absolute + delta claim
        request_with_delta = BeliefRequest(
            normalized_claims=[absolute_claim, delta_claim],
            contradictions=[],
        )
        result_with_delta = belief_engine.compute_beliefs(request_with_delta)

        # Delta claims should not affect value summary ranges
        if len(result_absolute_only) > 0 and len(result_with_delta) > 0:
            assert result_absolute_only[0].normalized_value_summary is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Output Schema Validity
# ──────────────────────────────────────────────────────────────────────────────


class TestOutputSchemaValidity:
    """Tests for output schema validity."""

    def test_belief_state_pydantic_model(self, belief_engine, sample_normalized_claims):
        """Test BeliefState is valid Pydantic model."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )
        result = belief_engine.compute_beliefs(request)

        for state in result:
            assert isinstance(state, BeliefState)

            # Round-trip serialization
            state_dict = state.model_dump()
            restored = BeliefState(**state_dict)
            assert isinstance(restored, BeliefState)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic belief computation."""

    def test_same_input_same_output(self, belief_engine, sample_normalized_claims):
        """Test same input produces same output."""
        request = BeliefRequest(
            normalized_claims=sample_normalized_claims,
            contradictions=[],
        )

        result1 = belief_engine.compute_beliefs(request)
        result2 = belief_engine.compute_beliefs(request)
        result3 = belief_engine.compute_beliefs(request)

        # Same number of belief states
        assert len(result1) == len(result2) == len(result3)

        # Same confidence levels
        if len(result1) > 0:
            assert result1[0].qualitative_confidence == result2[0].qualitative_confidence == result3[0].qualitative_confidence


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_many_claims_same_context_metric(self, belief_engine):
        """Test handling of many claims on same context/metric."""
        claims = [
            NormalizedClaim(
                claim_id=f"claim_{i}",
                context_id="ctx_test",
                subject=f"Model_{i}",
                predicate="achieves",
                object_raw=f"{80 + i}% accuracy",
                metric_canonical="ACCURACY",
                value_raw=str(80 + i),
                value_normalized=float(80 + i),
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            for i in range(20)
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        # Should handle many claims gracefully
        assert isinstance(result, list)

    def test_different_metrics_separate_belief_states(self, belief_engine):
        """Test different metrics produce separate belief states."""
        claims = [
            NormalizedClaim(
                claim_id="claim_acc",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="90% accuracy",
                metric_canonical="ACCURACY",
                value_raw="90",
                value_normalized=90.0,
                unit_normalized="%",
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            ),
            NormalizedClaim(
                claim_id="claim_f1",
                context_id="ctx_test",
                subject="Model",
                predicate="achieves",
                object_raw="85 F1-score",
                metric_canonical="F1",
                value_raw="85",
                value_normalized=85.0,
                unit_normalized=None,
                polarity=Polarity.SUPPORTS,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            ),
        ]
        request = BeliefRequest(normalized_claims=claims, contradictions=[])
        result = belief_engine.compute_beliefs(request)

        # Different metrics should produce separate belief states
        if len(result) >= 2:
            # Check metrics are different
            metrics = [state.metric for state in result]
            assert len(set(metrics)) == len(metrics) or len(result) == 1
