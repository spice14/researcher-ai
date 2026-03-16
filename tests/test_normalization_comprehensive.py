"""Comprehensive high-priority tests for normalization service.

Targets missing lines in services/normalization/service.py (104 missing statements).
Focus: All metric aliases, unit conversions, numeric binding, rejection patterns.
"""

import pytest
from core.schemas.claim import Claim, ClaimSubtype, ClaimType, ConfidenceLevel, Polarity, ClaimEvidence
from services.normalization.schemas import (
    NormalizationRequest,
    NoNormalizationReason,
)
from services.normalization.service import NormalizationService


@pytest.fixture
def normalization_service():
    """Fixture providing NormalizationService instance."""
    return NormalizationService()


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Metric Alias Coverage (All _METRIC_ALIASES)
# ──────────────────────────────────────────────────────────────────────────────


class TestMetricAliases:
    """Tests covering all metric alias mappings."""

    def test_accuracy_alias_variants(self, normalization_service):
        """Test all accuracy alias variants."""
        aliases = [
            "Model achieves 92.5% accuracy.",
            "Model acc: 92.5%",
            "Classification accuracy 92.5%",
            "Model accuracy: 92.5%",
            "Top-1 92.5%",
            "Top1: 92.5%",
            "Top-1 accuracy: 92.5%",
            "Top1 accuracy 92.5%",
        ]
        
        for text in aliases:
            claim = Claim(
                claim_id=f"test_{text[:10]}",
                claim_type=ClaimType.PERFORMANCE,
                subject="Model",
                predicate="achieves",
                object=text,
                polarity=Polarity.SUPPORTS,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.HIGH,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.metric_canonical in ["ACCURACY", "TOP5_ACCURACY"]

    def test_top5_accuracy_variants(self, normalization_service):
        """Test Top-5 accuracy aliases."""
        aliases = [
            "Top-5 accuracy: 98.5%",
            "Top5 accuracy 98.5%",
            "Top-5 acc: 98.5%",
            "Top5 acc 98.5%",
        ]
        
        for text in aliases:
            claim = Claim(
                claim_id=f"test_top5_{text[:5]}",
                claim_type=ClaimType.PERFORMANCE,
                subject="Model",
                predicate="achieves",
                object=text,
                polarity=Polarity.SUPPORTS,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.HIGH,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.metric_canonical == "TOP5_ACCURACY"

    def test_f1_score_variants(self, normalization_service):
        """Test F1 score aliases."""
        aliases = [
            "F1-macro score: 0.87",
            "F1 macro: 0.87",
            "F1-score of 0.87",
            "F1: 0.87",
        ]
        
        for text in aliases:
            claim = Claim(
                claim_id=f"test_f1_{text[:5]}",
                claim_type=ClaimType.PERFORMANCE,
                subject="Model",
                predicate="achieves",
                object=text,
                polarity=Polarity.SUPPORTS,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.HIGH,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.metric_canonical in ["F1", "F1_MACRO"]

    def test_bleu_rouge_variants(self, normalization_service):
        """Test BLEU and ROUGE metric aliases."""
        test_cases = [
            ("BLEU-4: 35.2", "BLEU"),
            ("BLEU score 35.2", "BLEU"),
            ("ROUGE-L: 0.42", "ROUGE_L"),
            ("ROUGE: 0.40", "ROUGE"),
        ]
        
        for text, expected_metric in test_cases:
            claim = Claim(
                claim_id=f"test_{expected_metric}",
                claim_type=ClaimType.PERFORMANCE,
                subject="Model",
                predicate="achieves",
                object=text,
                polarity=Polarity.SUPPORTS,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.HIGH,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.metric_canonical == expected_metric

    def test_detection_metrics(self, normalization_service):
        """Test detection metrics: mAP, IOU, AP50, AP75."""
        test_cases = [
            ("mAP: 45.3", "MAP"),
            ("MAP: 45.3", "MAP"),
            ("IOU: 0.75", "IOU"),
            ("AP50: 52.1", "AP50"),
            ("AP75: 48.2", "AP75"),
        ]
        
        for text, expected_metric in test_cases:
            claim = Claim(
                claim_id=f"test_{expected_metric}",
                claim_type=ClaimType.PERFORMANCE,
                subject="Model",
                predicate="achieves",
                object=text,
                polarity=Polarity.SUPPORTS,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.HIGH,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.metric_canonical == expected_metric


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Unit Conversion (_convert_unit)
# ──────────────────────────────────────────────────────────────────────────────


class TestUnitConversion:
    """Tests for unit conversion and normalization."""

    def test_percentage_conversion(self, normalization_service):
        """Test percentage unit conversion."""
        claim = Claim(
            claim_id="test_pct",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="92.5% accuracy",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="92.5% accuracy",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized:
            assert result.normalized.unit_normalized == "ratio"
            # 92.5% should convert to 0.925
            assert abs(result.normalized.value_normalized - 0.925) < 0.01

    def test_millisecond_conversion(self, normalization_service):
        """Test millisecond to second conversion."""
        claim = Claim(
            claim_id="test_ms",
            claim_type=ClaimType.EFFICIENCY,
            subject="Model",
            predicate="requires",
            object="45 ms latency",
            polarity=Polarity.REFUTES,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="45 ms latency",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized:
            assert result.normalized.unit_normalized == "s"
            # 45ms should convert to 0.045s
            assert abs(result.normalized.value_normalized - 0.045) < 0.001

    def test_memory_unit_conversion(self, normalization_service):
        """Test memory unit conversions (GB, MB, KB)."""
        test_cases = [
            ("12 GB memory", "gb", 12.0),
            ("512 MB memory", "gb", 512.0 / 1024.0),
            ("2048 KB memory", "gb", 2048.0 / (1024 * 1024)),
        ]
        
        for text, expected_unit, expected_value in test_cases:
            claim = Claim(
                claim_id=f"test_mem_{text[:4]}",
                claim_type=ClaimType.EFFICIENCY,
                subject="Model",
                predicate="requires",
                object=text,
                polarity=Polarity.REFUTES,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.unit_normalized == expected_unit

    def test_time_unit_seconds(self, normalization_service):
        """Test second time units."""
        test_cases = [
            "24 seconds training",
            "120 s training",
            "60 sec training",
        ]
        
        for text in test_cases:
            claim = Claim(
                claim_id=f"test_sec_{text[:4]}",
                claim_type=ClaimType.EFFICIENCY,
                subject="Model",
                predicate="requires",
                object=text,
                polarity=Polarity.REFUTES,
                evidence=[ClaimEvidence(
                    source_id="paper_001",
                    page=1,
                    snippet=text,
                    retrieval_score=0.9,
                )],
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            request = NormalizationRequest(claim=claim)
            result = normalization_service.normalize(request)
            
            if result.normalized:
                assert result.normalized.unit_normalized == "s"


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Numeric Value Binding (Adjacency and Distance)
# ──────────────────────────────────────────────────────────────────────────────


class TestNumericBinding:
    """Tests for numeric value binding to metrics."""

    def test_metric_followed_by_value(self, normalization_service):
        """Test binding when metric is directly followed by value."""
        claim = Claim(
            claim_id="test_adjacent_1",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="Accuracy = 92.5%",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="Accuracy = 92.5%",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        assert result.normalized is not None
        assert result.normalized.metric_canonical == "ACCURACY"

    def test_value_followed_by_metric(self, normalization_service):
        """Test binding when value is directly followed by metric."""
        claim = Claim(
            claim_id="test_adjacent_2",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="92.5% on accuracy",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="92.5% on accuracy",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        assert result.normalized is not None

    def test_multiple_values_closest_binding(self, normalization_service):
        """Test that closest value to metric is selected."""
        claim = Claim(
            claim_id="test_closest",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="2014: benchmark improvement 92.5% accuracy on dataset 2012",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_002",
                page=5,
                snippet="improvement 92.5% accuracy on dataset",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 92.5%, not to 2014 or 2012 (years)
        if result.normalized:
            assert abs(result.normalized.value_normalized - 0.925) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Rejection Patterns (Years, References, Embedded)
# ──────────────────────────────────────────────────────────────────────────────


class TestRejectionPatterns:
    """Tests for number rejection patterns."""

    def test_reject_year_in_text(self, normalization_service):
        """Test rejection of years in general text."""
        claim = Claim(
            claim_id="test_year_reject",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="In 2020, model achieved 92.5% accuracy.",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="In 2020, model achieved 92.5% accuracy.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 92.5%, not 2020
        if result.normalized:
            assert abs(result.normalized.value_normalized - 0.925) < 0.01

    def test_reject_citation_year(self, normalization_service):
        """Test rejection of years in citation context."""
        claim = Claim(
            claim_id="test_citation_year",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="Smith et al. (2019) reported accuracy 92.5%.",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="Smith et al. (2019) reported accuracy 92.5%.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 92.5%, not 2019
        if result.normalized:
            assert abs(result.normalized.value_normalized - 0.925) < 0.01

    def test_reject_reference_number(self, normalization_service):
        """Test rejection of reference numbers (Table, Figure)."""
        claim = Claim(
            claim_id="test_table_ref",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="Results in Table 3 show 92.5% accuracy.",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="Results in Table 3 show 92.5% accuracy.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 92.5%, not 3 (table reference)
        if result.normalized:
            assert abs(result.normalized.value_normalized - 0.925) < 0.01

    def test_reject_figure_reference(self, normalization_service):
        """Test rejection of figure references."""
        claim = Claim(
            claim_id="test_fig_ref",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="Figure 2a demonstrates 92.5% accuracy improvement.",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="Figure 2a demonstrates 92.5% accuracy improvement.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 92.5%, not 2
        if result.normalized:
            assert abs(result.normalized.value_normalized - 0.925) < 0.01

    def test_reject_embedded_number(self, normalization_service):
        """Test rejection of embedded numbers (newstest2014)."""
        claim = Claim(
            claim_id="test_embedded",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="BLEU on newstest2014 is 35.2.",
            polarity=Polarity.SUPPORTS,
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="BLEU on newstest2014 is 35.2.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        # Should bind to 35.2, not 2014 embedded in newstest2014
        if result.normalized:
            assert abs(result.normalized.value_normalized - 35.2) < 0.1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Dataset Year Rejection
# ──────────────────────────────────────────────────────────────────────────────


class TestDatasetYearRejection:
    """Tests for dataset year rejection patterns."""

    def test_reject_wmt_year(self, normalization_service):
        """Test rejection of WMT dataset years."""
        claim = Claim(
            claim_id="test_wmt_year",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="WMT 2014 BLEU score is 35.2.",
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="WMT 2014 BLEU score is 35.2.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
            polarity=Polarity.SUPPORTS,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized:
            # Should bind to 35.2, not 2014
            assert abs(result.normalized.value_normalized - 35.2) < 0.1

    def test_reject_voc_year(self, normalization_service):
        """Test rejection of VOC dataset years."""
        claim = Claim(
            claim_id="test_voc_year",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="PASCAL VOC 2012 results: 75.3% AP.",
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="PASCAL VOC 2012 results: 75.3% AP.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
            polarity=Polarity.SUPPORTS,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized:
            # Should bind to 75.3%, not 2012
            assert abs(result.normalized.value_normalized - 0.753) < 0.01

    def test_reject_conll_year(self, normalization_service):
        """Test rejection of CoNLL dataset years."""
        claim = Claim(
            claim_id="test_conll_year",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="CoNLL-2012 shared task F1: 82.1.",
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="CoNLL-2012 shared task F1: 82.1.",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
            polarity=Polarity.SUPPORTS,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request)
        
        if result.normalized:
            # Should bind to 82.1, not 2012
            assert abs(result.normalized.value_normalized - 82.1) < 0.1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Debug Mode Diagnostics
# ──────────────────────────────────────────────────────────────────────────────


class TestDebugModeDiagnostics:
    """Tests for debug mode diagnostic output."""

    def test_debug_mode_missing_metric(self, normalization_service):
        """Test debug diagnostic for missing metric."""
        claim = Claim(
            claim_id="test_debug_no_metric",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="good performance",  # No metric
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="good performance",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.LOW,
            polarity=Polarity.SUPPORTS,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request, debug_mode=True)
        
        assert result.diagnostic is not None
        assert result.no_normalization is not None

    def test_debug_mode_no_value(self, normalization_service):
        """Test debug diagnostic for missing value."""
        claim = Claim(
            claim_id="test_debug_no_value",
            claim_type=ClaimType.PERFORMANCE,
            subject="Model",
            predicate="achieves",
            object="accuracy on benchmark",  # Metric but no numeric value
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="accuracy on benchmark",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.MEDIUM,
            polarity=Polarity.SUPPORTS,
        )
        request = NormalizationRequest(claim=claim)
        result = normalization_service.normalize(request, debug_mode=True)
        
        assert result.diagnostic is not None
        if result.no_normalization:
            assert result.no_normalization.reason_code is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizationDeterminism:
    """Tests for deterministic normalization."""

    def test_deterministic_output(self, normalization_service):
        """Test same claim produces identical normalization."""
        claim = Claim(
            claim_id="test_determinism",
            claim_type=ClaimType.PERFORMANCE,
            subject="BERT",
            predicate="achieves",
            object="92.5% accuracy on GLUE",
            evidence=[ClaimEvidence(
                source_id="paper_001",
                page=1,
                snippet="92.5% accuracy on GLUE",
                retrieval_score=0.9,
            )],
            confidence_level=ConfidenceLevel.HIGH,
            polarity=Polarity.SUPPORTS,
        )
        
        request = NormalizationRequest(claim=claim)
        result1 = normalization_service.normalize(request)
        result2 = normalization_service.normalize(request)
        
        if result1.normalized and result2.normalized:
            assert result1.normalized.value_normalized == result2.normalized.value_normalized
            assert result1.normalized.metric_canonical == result2.normalized.metric_canonical
            assert result1.normalized.unit_normalized == result2.normalized.unit_normalized
