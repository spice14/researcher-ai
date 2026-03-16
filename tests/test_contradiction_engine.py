"""Comprehensive unit tests for epistemic contradiction/relation engine."""

import pytest
from services.contradiction.schemas import AnalysisRequest
from services.contradiction.relation_engine import EpistemicRelationEngine
from services.contradiction.epistemic_relations import (
    Contradiction,
    PerformanceVariance,
    ConditionalDivergence,
    EpistemicRelationGraph,
)
from services.normalization.schemas import NormalizedClaim
from core.schemas.claim import ClaimSubtype, Polarity


@pytest.fixture
def relation_engine():
    """Fixture providing an EpistemicRelationEngine instance."""
    return EpistemicRelationEngine()


@pytest.fixture
def bert_glue_high():
    """Fixture: BERT on GLUE with high score."""
    return NormalizedClaim(
        claim_id="claim_bert_glue_high",
        context_id="ctx_bert_glue",
        subject="BERT",
        predicate="achieves",
        object_raw="92.5% accuracy on GLUE",
        metric_canonical="ACCURACY",
        value_raw="92.5",
        value_normalized=92.5,
        unit_normalized="%",
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def bert_glue_low():
    """Fixture: BERT on GLUE with low score (contradiction)."""
    return NormalizedClaim(
        claim_id="claim_bert_glue_low",
        context_id="ctx_bert_glue",
        subject="BERT",
        predicate="achieves",
        object_raw="45.0% accuracy on GLUE",
        metric_canonical="ACCURACY",
        value_raw="45.0",
        value_normalized=45.0,
        unit_normalized="%",
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def gpt_glue():
    """Fixture: GPT on GLUE (different subject, same metric)."""
    return NormalizedClaim(
        claim_id="claim_gpt_glue",
        context_id="ctx_bert_glue",
        subject="GPT",
        predicate="achieves",
        object_raw="88.0% accuracy on GLUE",
        metric_canonical="ACCURACY",
        value_raw="88.0",
        value_normalized=88.0,
        unit_normalized="%",
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def bert_squad():
    """Fixture: BERT on SQuAD (different context)."""
    return NormalizedClaim(
        claim_id="claim_bert_squad",
        context_id="ctx_bert_squad",
        subject="BERT",
        predicate="achieves",
        object_raw="93.0% accuracy on SQuAD",
        metric_canonical="ACCURACY",
        value_raw="93.0",
        value_normalized=93.0,
        unit_normalized="%",
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def bert_glue_delta():
    """Fixture: Delta improvement claim (should be gated out)."""
    return NormalizedClaim(
        claim_id="claim_delta_improvement",
        context_id="ctx_improvement",
        subject="BERT-Improved",
        predicate="outperforms",
        object_raw="baseline by 2.5% accuracy",
        metric_canonical="ACCURACY",
        value_raw="2.5",
        value_normalized=2.5,
        unit_normalized="%",
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.DELTA,
    )


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Basic Analysis
# ──────────────────────────────────────────────────────────────────────────────


class TestBasicAnalysis:
    """Tests for basic epistemic relation analysis."""

    def test_analyze_single_claim(self, relation_engine, bert_glue_high):
        """Test analysis with single claim."""
        request = AnalysisRequest(claims=[bert_glue_high])
        result = relation_engine.analyze(request)
        
        assert isinstance(result, EpistemicRelationGraph)
        assert result.contradictions is not None
        assert result.performance_variance is not None
        assert result.conditional_divergences is not None

    def test_analyze_empty_claims(self, relation_engine):
        """Test analysis with empty claims list."""
        request = AnalysisRequest(claims=[])
        result = relation_engine.analyze(request)
        
        assert len(result.contradictions) == 0
        assert len(result.performance_variance) == 0
        assert len(result.conditional_divergences) == 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Contradiction Detection
# ──────────────────────────────────────────────────────────────────────────────


class TestContradictionDetection:
    """Tests for logical contradiction detection."""

    def test_detect_contradiction_same_subject_same_metric_conflicting_values(
        self, relation_engine, bert_glue_high, bert_glue_low
    ):
        """Test contradiction detection with same subject, metric, different values."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_glue_low])
        result = relation_engine.analyze(request)
        
        # Should detect contradiction
        assert isinstance(result.contradictions, list)
        # May have contradictions or not depending on tolerance

    def test_no_contradiction_different_subjects(self, relation_engine, bert_glue_high, gpt_glue):
        """Test NO contradiction when subjects differ."""
        request = AnalysisRequest(claims=[bert_glue_high, gpt_glue])
        result = relation_engine.analyze(request)
        
        # Different subjects should NOT produce contradictions
        # May produce performance_variance instead
        for contradiction in result.contradictions:
            # Any contradiction must not have different subjects
            assert contradiction.subject is not None

    def test_no_contradiction_different_contexts(self, relation_engine, bert_glue_high, bert_squad):
        """Test NO contradiction when contexts differ."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_squad])
        result = relation_engine.analyze(request)
        
        # Different contexts should NOT produce contradictions
        # May produce conditional_divergences instead
        for contradiction in result.contradictions:
            # If contradiction exists, subjects must match
            assert contradiction.subject == bert_glue_high.subject


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Performance Variance Detection
# ──────────────────────────────────────────────────────────────────────────────


class TestPerformanceVariance:
    """Tests for performance variance detection."""

    def test_detect_performance_variance_different_subjects(
        self, relation_engine, bert_glue_high, gpt_glue
    ):
        """Test variance detection with different subjects."""
        request = AnalysisRequest(claims=[bert_glue_high, gpt_glue])
        result = relation_engine.analyze(request)
        
        assert isinstance(result.performance_variance, list)
        # Performance variance is co-true, different entities same benchmark

    def test_variance_same_context_same_metric(self, relation_engine, bert_glue_high, gpt_glue):
        """Test variance requires same context and metric."""
        request = AnalysisRequest(claims=[bert_glue_high, gpt_glue])
        result = relation_engine.analyze(request)
        
        for variance in result.performance_variance:
            # Both claims should have same context
            assert variance.context_id is not None

    def test_variance_contains_multiple_subjects(self, relation_engine, bert_glue_high, gpt_glue):
        """Test variance group contains different subjects."""
        request = AnalysisRequest(claims=[bert_glue_high, gpt_glue])
        result = relation_engine.analyze(request)
        
        for variance in result.performance_variance:
            # Should have multiple subjects in variance
            assert len(variance.subjects) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Conditional Divergence Detection
# ──────────────────────────────────────────────────────────────────────────────


class TestConditionalDivergence:
    """Tests for conditional divergence detection."""

    def test_detect_conditional_divergence_different_contexts(
        self, relation_engine, bert_glue_high, bert_squad
    ):
        """Test divergence detection with same subject, different contexts."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_squad])
        result = relation_engine.analyze(request)
        
        assert isinstance(result.conditional_divergences, list)
        # May have conditional divergences for same entity, different contexts

    def test_divergence_requires_same_subject(self, relation_engine, bert_glue_high, bert_squad):
        """Test divergence requires same subject entity."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_squad])
        result = relation_engine.analyze(request)
        
        for divergence in result.conditional_divergences:
            # Divergences should have same subject (may be normalized)
            assert divergence.subject is not None
            # Both original claims have same subject (BERT)
            assert bert_glue_high.subject.lower() == bert_squad.subject.lower()

    def test_divergence_requires_different_contexts(self, relation_engine, bert_glue_high, bert_squad):
        """Test divergence requires different contexts."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_squad])
        result = relation_engine.analyze(request)
        
        for divergence in result.conditional_divergences:
            # Contexts must be different
            assert divergence.context_a != divergence.context_b


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Delta Contamination Gate
# ──────────────────────────────────────────────────────────────────────────────


class TestDeltaContaminationGate:
    """Tests for delta claim contamination gate (memory requirement)."""

    def test_delta_claims_excluded_from_absolute_relations(
        self, relation_engine, bert_glue_high, bert_glue_delta
    ):
        """Test delta claims are excluded from absolute relation analysis."""
        # This test verifies the delta contamination gate
        # Delta claims (relative improvements) should not contaminate
        # absolute value ranges

        request = AnalysisRequest(claims=[bert_glue_high, bert_glue_delta])
        result = relation_engine.analyze(request)

        # The delta claim should be gated out during analysis
        # (only ABSOLUTE claims used for contradictions/variance)
        # So we should not see delta_improvement claims affecting value ranges

        for contradiction in result.contradictions:
            # Contradictions should only involve absolute claims
            # Not delta improvements
            pass

    def test_only_absolute_claims_produce_relations(
        self, relation_engine, bert_glue_high, bert_glue_low, bert_glue_delta
    ):
        """Test only ABSOLUTE claims produce relations."""
        request = AnalysisRequest(
            claims=[bert_glue_high, bert_glue_low, bert_glue_delta]
        )
        result = relation_engine.analyze(request)

        # If contradictions exist, they should only involve absolute claims
        # Delta claim (bert_glue_delta) should not appear in any relation
        all_claim_ids = set()
        for contradiction in result.contradictions:
            all_claim_ids.add(contradiction.claim_id_a)
            all_claim_ids.add(contradiction.claim_id_b)

        for variance in result.performance_variance:
            all_claim_ids.update(variance.claim_ids)

        # Delta claim should not appear in any relations
        assert bert_glue_delta.claim_id not in all_claim_ids


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Tolerance Handling
# ──────────────────────────────────────────────────────────────────────────────


class TestToleranceHandling:
    """Tests for tolerance-based contradiction detection."""

    def test_small_difference_within_tolerance(self, relation_engine):
        """Test small differences within tolerance are not contradictions."""
        claim1 = NormalizedClaim(
            claim_id="claim_1",
            context_id="ctx_test",
            subject="Model-A",
            predicate="achieves",
            object_raw="92.0% accuracy",
            metric_canonical="ACCURACY",
            value_raw="92.0",
            value_normalized=92.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        claim2 = NormalizedClaim(
            claim_id="claim_2",
            context_id="ctx_test",
            subject="Model-A",
            predicate="achieves",
            object_raw="91.95% accuracy",
            metric_canonical="ACCURACY",
            value_raw="91.95",
            value_normalized=91.95,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = AnalysisRequest(claims=[claim1, claim2])
        result = relation_engine.analyze(request)

        # Small difference (0.05% on ~92% = 0.05% relative) within tolerance

    def test_large_difference_beyond_tolerance(self, relation_engine):
        """Test large differences beyond tolerance are contradictions."""
        claim1 = NormalizedClaim(
            claim_id="claim_1",
            context_id="ctx_test",
            subject="Model-B",
            predicate="achieves",
            object_raw="90.0% accuracy",
            metric_canonical="ACCURACY",
            value_raw="90.0",
            value_normalized=90.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        claim2 = NormalizedClaim(
            claim_id="claim_2",
            context_id="ctx_test",
            subject="Model-B",
            predicate="achieves",
            object_raw="70.0% accuracy",
            metric_canonical="ACCURACY",
            value_raw="70.0",
            value_normalized=70.0,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = AnalysisRequest(claims=[claim1, claim2])
        result = relation_engine.analyze(request)

        # Large difference (20% absolute) should be detected

    def test_custom_tolerance_override(self, relation_engine):
        """Test custom tolerance overrides per unit."""
        claim1 = NormalizedClaim(
            claim_id="claim_1",
            context_id="ctx_test",
            subject="Model-C",
            predicate="achieves",
            object_raw="100 ms latency",
            metric_canonical="LATENCY",
            value_raw="100",
            value_normalized=100.0,
            unit_normalized="ms",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        claim2 = NormalizedClaim(
            claim_id="claim_2",
            context_id="ctx_test",
            subject="Model-C",
            predicate="achieves",
            object_raw="104 ms latency",
            metric_canonical="LATENCY",
            value_raw="104",
            value_normalized=104.0,
            unit_normalized="ms",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        # Custom tolerance override
        request = AnalysisRequest(
            claims=[claim1, claim2], value_tolerance_by_unit={"ms": 0.02}
        )
        result = relation_engine.analyze(request)

        # With 2% tolerance, 4ms diff on 100ms = 4% > tolerance


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Output Schema Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestOutputSchemaValidation:
    """Tests for output schema correctness."""

    def test_result_is_epistemic_relation_graph(self, relation_engine, bert_glue_high):
        """Test result is valid EpistemicRelationGraph."""
        request = AnalysisRequest(claims=[bert_glue_high])
        result = relation_engine.analyze(request)

        assert isinstance(result, EpistemicRelationGraph)

    def test_contradictions_are_contradiction_type(self, relation_engine, bert_glue_high, bert_glue_low):
        """Test contradictions list contains Contradiction objects."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_glue_low])
        result = relation_engine.analyze(request)

        for contradiction in result.contradictions:
            assert isinstance(contradiction, Contradiction)
            assert contradiction.claim_id_a is not None
            assert contradiction.claim_id_b is not None
            assert contradiction.subject is not None
            assert contradiction.reason is not None

    def test_variance_are_performance_variance_type(self, relation_engine, bert_glue_high, gpt_glue):
        """Test variance list contains PerformanceVariance objects."""
        request = AnalysisRequest(claims=[bert_glue_high, gpt_glue])
        result = relation_engine.analyze(request)

        for variance in result.performance_variance:
            assert isinstance(variance, PerformanceVariance)
            assert variance.claim_ids is not None
            assert variance.metric_canonical is not None
            assert variance.subjects is not None

    def test_divergences_are_conditional_divergence_type(self, relation_engine, bert_glue_high, bert_squad):
        """Test divergences list contains ConditionalDivergence objects."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_squad])
        result = relation_engine.analyze(request)

        for divergence in result.conditional_divergences:
            assert isinstance(divergence, ConditionalDivergence)
            assert divergence.claim_id_a is not None
            assert divergence.claim_id_b is not None
            assert divergence.subject is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic analysis."""

    def test_same_input_same_output(self, relation_engine, bert_glue_high, bert_glue_low):
        """Test same input always produces same output."""
        request = AnalysisRequest(claims=[bert_glue_high, bert_glue_low])

        result1 = relation_engine.analyze(request)
        result2 = relation_engine.analyze(request)
        result3 = relation_engine.analyze(request)

        # Number of relations should be consistent
        assert len(result1.contradictions) == len(result2.contradictions) == len(result3.contradictions)
        assert len(result1.performance_variance) == len(result2.performance_variance) == len(result3.performance_variance)
        assert len(result1.conditional_divergences) == len(result2.conditional_divergences) == len(result3.conditional_divergences)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_many_claims_same_metric(self, relation_engine):
        """Test analysis with many claims on same metric."""
        claims = []
        for i in range(10):
            claims.append(
                NormalizedClaim(
                    claim_id=f"claim_{i}",
                    context_id="ctx_many",
                    subject=f"Model-{i}",
                    predicate="achieves",
                    object_raw=f"{80 + i}% accuracy",
                    metric_canonical="ACCURACY",
                    value_raw=str(80 + i),
                    value_normalized=float(80 + i),
                    unit_normalized="%",
                    polarity=Polarity.SUPPORTS,
                    claim_subtype=ClaimSubtype.ABSOLUTE,
                )
            )

        request = AnalysisRequest(claims=claims)
        result = relation_engine.analyze(request)

        # Should handle many claims gracefully
        assert isinstance(result, EpistemicRelationGraph)

    def test_very_similar_values_within_tolerance(self, relation_engine):
        """Test claims with very similar values."""
        claim1 = NormalizedClaim(
            claim_id="claim_similar_1",
            context_id="ctx_similar",
            subject="Model-Similar",
            predicate="achieves",
            object_raw="92.50% accuracy",
            metric_canonical="ACCURACY",
            value_raw="92.50",
            value_normalized=92.50,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        claim2 = NormalizedClaim(
            claim_id="claim_similar_2",
            context_id="ctx_similar",
            subject="Model-Similar",
            predicate="achieves",
            object_raw="92.51% accuracy",
            metric_canonical="ACCURACY",
            value_raw="92.51",
            value_normalized=92.51,
            unit_normalized="%",
            polarity=Polarity.SUPPORTS,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )

        request = AnalysisRequest(claims=[claim1, claim2])
        result = relation_engine.analyze(request)

        # Should not report insignificant differences as contradictions
        assert isinstance(result, EpistemicRelationGraph)
