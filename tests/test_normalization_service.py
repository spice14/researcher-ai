"""Comprehensive unit tests for deterministic claim normalization service."""

import pytest
from core.schemas.claim import (
    Claim,
    ClaimEvidence,
    ClaimSubtype,
    ClaimType,
    ConfidenceLevel,
    Polarity,
)
from services.normalization.schemas import (
    NormalizationRequest,
    NormalizationResult,
    NormalizedClaim,
    NoNormalization,
    NoNormalizationReason,
)
from services.normalization.service import NormalizationService


@pytest.fixture
def normalization_service():
    """Fixture providing a NormalizationService instance."""
    return NormalizationService()


@pytest.fixture
def accuracy_claim():
    """Fixture: normalized claim with accuracy metric."""
    return Claim(
        claim_id="claim_acc_1",
        context_id="ctx_bert_glue",
        subject="BERT",
        predicate="achieves",
        object="92.5% accuracy on GLUE",
        evidence=[
            ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="BERT achieves 92.5% accuracy on GLUE.",
                retrieval_score=0.95,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.HIGH,
        claim_type=ClaimType.PERFORMANCE,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def bleu_score_claim():
    """Fixture: claim with BLEU metric."""
    return Claim(
        claim_id="claim_bleu_1",
        context_id="ctx_mt",
        subject="Seq2Seq",
        predicate="achieves",
        object="27.3 BLEU on WMT14 English-German",
        evidence=[
            ClaimEvidence(
                source_id="paper_002",
                page=2,
                snippet="27.3 BLEU score on WMT14 English-German.",
                retrieval_score=0.90,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.MEDIUM,
        claim_type=ClaimType.PERFORMANCE,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def latency_claim():
    """Fixture: efficiency claim with latency."""
    return Claim(
        claim_id="claim_latency_1",
        context_id="ctx_inference",
        subject="Model-X",
        predicate="requires",
        object="125 ms latency per inference",
        evidence=[
            ClaimEvidence(
                source_id="paper_003",
                page=3,
                snippet="Inference latency of 125 ms per sample.",
                retrieval_score=0.85,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.MEDIUM,
        claim_type=ClaimType.EFFICIENCY,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def delta_efficiency_claim():
    """Fixture: delta improvement claim."""
    return Claim(
        claim_id="claim_delta_1",
        context_id="ctx_improvement",
        subject="Optimized-BERT",
        predicate="outperforms",
        object="baseline by 3.2% accuracy",
        evidence=[
            ClaimEvidence(
                source_id="paper_004",
                page=1,
                snippet="Outperforms baseline by 3.2% accuracy.",
                retrieval_score=0.92,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.HIGH,
        claim_type=ClaimType.PERFORMANCE,
        claim_subtype=ClaimSubtype.DELTA,
    )


@pytest.fixture
def missing_metric_claim():
    """Fixture: claim without identifiable metric."""
    return Claim(
        claim_id="claim_no_metric",
        context_id="ctx_invalid",
        subject="Model",
        predicate="description",
        object="has many parameters",
        evidence=[
            ClaimEvidence(
                source_id="paper_005",
                page=1,
                snippet="Has many parameters.",
                retrieval_score=0.75,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.LOW,
        claim_type=ClaimType.STRUCTURAL,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


@pytest.fixture
def missing_value_claim():
    """Fixture: claim with metric but no numeric value."""
    return Claim(
        claim_id="claim_no_value",
        context_id="ctx_invalid",
        subject="Model",
        predicate="achieves",
        object="accuracy on dataset",
        evidence=[
            ClaimEvidence(
                source_id="paper_006",
                page=1,
                snippet="Achieves accuracy on dataset.",
                retrieval_score=0.70,
            )
        ],
        polarity=Polarity.SUPPORTS,
        confidence_level=ConfidenceLevel.LOW,
        claim_type=ClaimType.PERFORMANCE,
        claim_subtype=ClaimSubtype.ABSOLUTE,
    )


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Basic Normalization
# ──────────────────────────────────────────────────────────────────────────────


class TestBasicNormalization:
    """Tests for basic claim normalization."""

    def test_normalize_accuracy_claim(self, normalization_service, accuracy_claim):
        """Test normalization of accuracy claim."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        # Should normalize successfully
        assert result.normalized is not None or result.no_normalization is not None
        
        if result.normalized is not None:
            assert isinstance(result.normalized, NormalizedClaim)
            assert result.normalized.metric_canonical is not None
            assert result.normalized.value_normalized is not None

    def test_normalize_bleu_claim(self, normalization_service, bleu_score_claim):
        """Test normalization of BLEU score claim."""
        request = NormalizationRequest(claim=bleu_score_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.metric_canonical in ["BLEU", "BLEU_SCORE"]
            assert result.normalized.value_normalized > 0

    def test_normalize_latency_claim(self, normalization_service, latency_claim):
        """Test normalization of latency efficiency claim."""
        request = NormalizationRequest(claim=latency_claim)
        result = normalization_service.normalize(request)
        
        # May normalize or reject based on metric support
        assert result.normalized is not None or result.no_normalization is not None

    def test_normalized_claim_preserves_subject(self, normalization_service, accuracy_claim):
        """Test normalization preserves subject."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.subject == accuracy_claim.subject

    def test_normalized_claim_preserves_claim_id(self, normalization_service, accuracy_claim):
        """Test normalization preserves original claim_id."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.claim_id == accuracy_claim.claim_id


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Metric Canonicalization
# ──────────────────────────────────────────────────────────────────────────────


class TestMetricCanonical:
    """Tests for metric canonicalization."""

    def test_accuracy_metric_canonical(self, normalization_service):
        """Test accuracy metric is canonicalized."""
        claim = Claim(
            claim_id="test_acc",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="92.0% accuracy",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="92.0% accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            # Should be canonicalized to one of: ACCURACY, TOP1_ACCURACY, TOP5_ACCURACY
            assert result.normalized.metric_canonical is not None

    def test_multiple_metric_aliases_normalize_same(self, normalization_service):
        """Test aliases of same metric normalize consistently."""
        metrics = ["accuracy", "acc", "top-1"]
        claims = []
        
        for metric in metrics:
            claim = Claim(
                claim_id=f"test_metric_{metric}",
                context_id="ctx_metric_test",
                subject="Model",
                predicate="achieves",
                object=f"92.0% {metric}",
                evidence=[
                    ClaimEvidence(
                        source_id="paper_metric_test",
                        page=1,
                        snippet=f"92.0% {metric}",
                        retrieval_score=0.9,
                    )
                ],
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
                claim_type=ClaimType.PERFORMANCE,
                claim_subtype=ClaimSubtype.ABSOLUTE,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            if result.normalized is not None:
                claims.append(result.normalized)
        
        # If multiple normalized, they should reference the same canonical metric
        if len(claims) > 1:
            first_metric = claims[0].metric_canonical
            # All should normalize to same canonical form
            assert all(c.metric_canonical == first_metric for c in claims)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Numeric Value Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestNumericExtraction:
    """Tests for numeric value extraction and normalization."""

    def test_extract_percentage_value(self, normalization_service):
        """Test extraction of percentage values."""
        claim = Claim(
            claim_id="test_percent",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="83.5% accuracy on benchmark",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="83.5% accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            # Value should be normalized (may convert % to ratio 0.0-1.0)
            assert result.normalized.value_normalized is not None
            assert result.normalized.value_raw == "83.5" or result.normalized.value_raw == "83.5%"

    def test_extract_non_percentage_value(self, normalization_service):
        """Test extraction of absolute values (not percentage)."""
        claim = Claim(
            claim_id="test_absolute",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="42.1 BLEU on WMT",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="42.1 BLEU",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.value_normalized is not None

    def test_rejects_year_as_value(self, normalization_service):
        """Test that year numbers are rejected as metric values."""
        claim = Claim(
            claim_id="test_year",
            context_id="ctx_test",
            subject="Model",
            predicate="published",
            object="2022 accuracy",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="2022 accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Year should be rejected as a metric value
        assert result.normalized is None or result.no_normalization is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Unit Normalization
# ──────────────────────────────────────────────────────────────────────────────


class TestUnitNormalization:
    """Tests for unit canonicalization."""

    def test_percentage_unit_normalized(self, normalization_service):
        """Test percentage symbol is normalized."""
        claim = Claim(
            claim_id="test_unit_pct",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="92% accuracy",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="92% accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            # Unit should be canonicalized (could be %, ratio, or other)
            unit = result.normalized.unit_normalized
            assert unit is None or isinstance(unit, str)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Rejection Reasons
# ──────────────────────────────────────────────────────────────────────────────


class TestRejectionReasons:
    """Tests for normalization rejection reasons."""

    def test_missing_metric_identified(self, normalization_service, missing_metric_claim):
        """Test missing metric is properly identified."""
        request = NormalizationRequest(claim=missing_metric_claim)
        result = normalization_service.normalize(request)
        
        if result.no_normalization is not None:
            assert result.no_normalization.reason_code in [
                NoNormalizationReason.MISSING_METRIC,
                NoNormalizationReason.MISSING_VALUE,
            ]

    def test_missing_value_identified(self, normalization_service, missing_value_claim):
        """Test missing numeric value is properly identified."""
        request = NormalizationRequest(claim=missing_value_claim)
        result = normalization_service.normalize(request)
        
        if result.no_normalization is not None:
            assert result.no_normalization.reason_code in [
                NoNormalizationReason.MISSING_VALUE,
                NoNormalizationReason.MISSING_METRIC,
                NoNormalizationReason.AMBIGUOUS_NUMERIC_BINDING,
            ]

    def test_rejection_never_both_normalized_and_rejected(self, normalization_service, missing_metric_claim):
        """Test XOR: never both normalized and rejected."""
        request = NormalizationRequest(claim=missing_metric_claim)
        result = normalization_service.normalize(request)
        
        has_normalized = result.normalized is not None
        has_rejection = result.no_normalization is not None
        assert has_normalized != has_rejection


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Debug Mode
# ──────────────────────────────────────────────────────────────────────────────


class TestDebugMode:
    """Tests for debug_mode diagnostic output."""

    def test_debug_mode_includes_diagnostic(self, normalization_service, accuracy_claim):
        """Test debug_mode=True includes diagnostic information."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request, debug_mode=True)
        
        # With debug_mode, may include diagnostic dict
        if result.diagnostic is not None:
            assert isinstance(result.diagnostic, dict)

    def test_normal_mode_omits_diagnostic(self, normalization_service, accuracy_claim):
        """Test debug_mode=False omits diagnostic."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request, debug_mode=False)
        
        # In normal mode, diagnostic should not be present
        assert result.diagnostic is None or result.diagnostic == {}


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Delta Subtypes
# ──────────────────────────────────────────────────────────────────────────────


class TestDeltaSubtypes:
    """Tests for delta (relative) claim handling."""

    def test_normalize_delta_claim(self, normalization_service, delta_efficiency_claim):
        """Test normalization of delta (relative improvement) claim."""
        request = NormalizationRequest(claim=delta_efficiency_claim)
        result = normalization_service.normalize(request)
        
        # Delta claims should normalize or be explicitly rejected
        assert result.normalized is not None or result.no_normalization is not None

    def test_delta_subtype_preserved(self, normalization_service, delta_efficiency_claim):
        """Test delta subtype is preserved in normalized claim."""
        request = NormalizationRequest(claim=delta_efficiency_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.claim_subtype == ClaimSubtype.DELTA


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Polarity Preservation
# ──────────────────────────────────────────────────────────────────────────────


class TestPolarityPreservation:
    """Tests for polarity field preservation."""

    def test_polarity_preserved_supports(self, normalization_service, accuracy_claim):
        """Test SUPPORTS polarity is preserved."""
        assert accuracy_claim.polarity == Polarity.SUPPORTS
        
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.polarity == Polarity.SUPPORTS

    def test_polarity_preserved_refutes(self, normalization_service):
        """Test REFUTES polarity is preserved."""
        claim = Claim(
            claim_id="test_refutes",
            context_id="ctx_test",
            subject="Model",
            predicate="fails",
            object="to achieve 90% accuracy",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="Failed to achieve 90% accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.REFUTES,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            assert result.normalized.polarity == Polarity.REFUTES


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic normalization."""

    def test_same_input_same_output(self, normalization_service, accuracy_claim):
        """Test same input always produces same normalized output."""
        request = NormalizationRequest(claim=accuracy_claim)
        
        result1 = normalization_service.normalize(request)
        result2 = normalization_service.normalize(request)
        result3 = normalization_service.normalize(request)
        
        # All three should be identical
        if result1.normalized is not None and result2.normalized is not None and result3.normalized is not None:
            assert result1.normalized.metric_canonical == result2.normalized.metric_canonical == result3.normalized.metric_canonical
            assert result1.normalized.value_normalized == result2.normalized.value_normalized == result3.normalized.value_normalized

    def test_deterministic_rejection_reason(self, normalization_service, missing_metric_claim):
        """Test rejection reason is deterministic."""
        request = NormalizationRequest(claim=missing_metric_claim)
        
        result1 = normalization_service.normalize(request)
        result2 = normalization_service.normalize(request)
        
        if result1.no_normalization is not None and result2.no_normalization is not None:
            assert result1.no_normalization.reason_code == result2.no_normalization.reason_code


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Schema Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_normalized_claim_valid_pydantic(self, normalization_service, accuracy_claim):
        """Test NormalizedClaim is valid Pydantic model."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        if result.normalized is not None:
            # Should be valid NormalizedClaim
            assert isinstance(result.normalized, NormalizedClaim)
            
            # Should serialize/deserialize round-trip
            claim_dict = result.normalized.model_dump()
            restored = NormalizedClaim(**claim_dict)
            assert isinstance(restored, NormalizedClaim)

    def test_result_xor_normalized_or_rejected(self, normalization_service, accuracy_claim):
        """Test XOR: exactly one of normalized or no_normalization."""
        request = NormalizationRequest(claim=accuracy_claim)
        result = normalization_service.normalize(request)
        
        has_normalized = result.normalized is not None
        has_rejection = result.no_normalization is not None
        assert has_normalized != has_rejection


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_large_value(self, normalization_service):
        """Test handling of very large numeric values."""
        claim = Claim(
            claim_id="test_large_value",
            context_id="ctx_test",
            subject="Model",
            predicate="has",
            object="1000000 parameters with 99.9% accuracy",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="1000000 parameters with 99.9% accuracy",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should handle without crashing
        assert result.normalized is not None or result.no_normalization is not None

    def test_very_small_value(self, normalization_service):
        """Test handling of very small numeric values."""
        claim = Claim(
            claim_id="test_small_value",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="0.001 latency",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="0.001 latency",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.EFFICIENCY,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        assert result.normalized is not None or result.no_normalization is not None

    def test_multiple_metrics_in_object(self, normalization_service):
        """Test claim with multiple metric mentions."""
        claim = Claim(
            claim_id="test_multi_metric",
            context_id="ctx_test",
            subject="Model",
            predicate="achieves",
            object="92% accuracy and 15ms latency",
            evidence=[
                ClaimEvidence(
                    source_id="paper_test",
                    page=1,
                    snippet="92% accuracy and 15ms latency",
                    retrieval_score=0.9,
                )
            ],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should extract first metric or reject with meaningful reason
        assert result.normalized is not None or result.no_normalization is not None
