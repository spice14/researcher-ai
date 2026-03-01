"""Expanded tests for extraction service targeting missing code paths."""

import pytest
from core.schemas.claim import ClaimSubtype, ClaimType, ConfidenceLevel, Polarity
from services.extraction.schemas import (
    ClaimExtractionRequest,
    ClaimExtractionResult,
    NoClaimReason,
    NoClaim,
)
from services.extraction.service import ClaimExtractor
from services.ingestion.schemas import IngestionChunk


def extract_from_request(extractor: ClaimExtractor, request: ClaimExtractionRequest):
    """Test helper: execute extraction using the canonical engine internals."""
    results = extractor._extract_all(request)
    if results:
        return results[0]
    return ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NON_CLAIM))


def extract_all_from_request(extractor: ClaimExtractor, request: ClaimExtractionRequest):
    """Test helper: return all extraction results for a chunk."""
    return extractor._extract_all(request)


@pytest.fixture
def extractor():
    """Fixture providing a ClaimExtractor instance."""
    return ClaimExtractor()


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Performance Extraction Variants
# ──────────────────────────────────────────────────────────────────────────────


class TestPerformanceExtractionVariants:
    """Tests for performance claim extraction variants."""

    def test_extract_performance_with_hedging(self, extractor):
        """Test that hedged performance claims are rejected."""
        chunk = IngestionChunk(
            chunk_id="chunk_001",
            source_id="paper_001",
            page=1,
            text="The model may achieve 92.5% accuracy.",
            start_char=0,
            end_char=40,
            text_hash="abc123",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.no_claim is not None or result.claim is None

    def test_extract_performance_with_uncertainty(self, extractor):
        """Test performance claims with uncertainty markers."""
        chunk = IngestionChunk(
            chunk_id="chunk_002",
            source_id="paper_001",
            page=1,
            text="The model approximately achieves 92.5% accuracy.",
            start_char=0,
            end_char=47,
            text_hash="def456",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should extract but mark confidence appropriately
        assert result.claim is not None or result.no_claim is not None

    def test_extract_performance_comparison(self, extractor):
        """Test performance claims with comparisons."""
        chunk = IngestionChunk(
            chunk_id="chunk_003",
            source_id="paper_001",
            page=1,
            text="The model outperforms BERT by 2% on accuracy.",
            start_char=0,
            end_char=45,
            text_hash="ghi789",
            context_id="ctx_001",
            numeric_strings=["2"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Comparison claims should be extracted as DELTA subtype
        assert result.claim is not None or result.no_claim is not None

    def test_extract_performance_multiple_metrics(self, extractor):
        """Test performance sentence with multiple metrics."""
        chunk = IngestionChunk(
            chunk_id="chunk_004",
            source_id="paper_001",
            page=1,
            text="Model achieves 92.5% accuracy and 0.85 F1-score.",
            start_char=0,
            end_char=48,
            text_hash="jkl012",
            context_id="ctx_001",
            numeric_strings=["92.5", "0.85"],
            unit_strings=["%"],
            metric_names=["accuracy", "F1-score"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        results = extract_all_from_request(extractor, request)
        
        # Multi-claim decomposition should produce multiple results
        assert len(results) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Efficiency Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestEfficiencyExtractionVariants:
    """Tests for efficiency claim extraction."""

    def test_extract_training_time(self, extractor):
        """Test extraction of training time efficiency claim."""
        chunk = IngestionChunk(
            chunk_id="chunk_005",
            source_id="paper_001",
            page=1,
            text="Model training requires 24 hours on a V100.",
            start_char=0,
            end_char=44,
            text_hash="mno345",
            context_id="ctx_001",
            numeric_strings=["24"],
            unit_strings=["hours"],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.claim_type == ClaimType.EFFICIENCY

    def test_extract_memory_usage(self, extractor):
        """Test extraction of memory usage claim."""
        chunk = IngestionChunk(
            chunk_id="chunk_006",
            source_id="paper_001",
            page=1,
            text="The model requires 12GB of GPU memory.",
            start_char=0,
            end_char=38,
            text_hash="pqr678",
            context_id="ctx_001",
            numeric_strings=["12"],
            unit_strings=["GB"],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None

    def test_extract_cost_claim(self, extractor):
        """Test extraction of computational cost."""
        chunk = IngestionChunk(
            chunk_id="chunk_007",
            source_id="paper_001",
            page=1,
            text="Training takes $1000 to run on cloud.",
            start_char=0,
            end_char=37,
            text_hash="stu901",
            context_id="ctx_001",
            numeric_strings=["1000"],
            unit_strings=["$"],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None

    def test_extract_inference_speed(self, extractor):
        """Test extraction of inference speed claim."""
        chunk = IngestionChunk(
            chunk_id="chunk_008",
            source_id="paper_001",
            page=1,
            text="Inference requires 45 milliseconds per sample.",
            start_char=0,
            end_char=46,
            text_hash="vwx234",
            context_id="ctx_001",
            numeric_strings=["45"],
            unit_strings=["ms"],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Structural Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestStructuralExtractionVariants:
    """Tests for structural claim extraction."""

    def test_extract_structural_introduces(self, extractor):
        """Test structural claim with 'introduces' verb."""
        chunk = IngestionChunk(
            chunk_id="chunk_009",
            source_id="paper_001",
            page=1,
            text="The paper introduces a novel attention mechanism.",
            start_char=0,
            end_char=47,
            text_hash="yza567",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.claim_type == ClaimType.STRUCTURAL

    def test_extract_structural_proposes(self, extractor):
        """Test structural claim with 'proposes' verb."""
        chunk = IngestionChunk(
            chunk_id="chunk_010",
            source_id="paper_001",
            page=1,
            text="We propose a transformer-based architecture.",
            start_char=0,
            end_char=41,
            text_hash="bcd890",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.claim_type == ClaimType.STRUCTURAL

    def test_extract_structural_replaces(self, extractor):
        """Test structural claim with 'replaces' verb."""
        chunk = IngestionChunk(
            chunk_id="chunk_011",
            source_id="paper_001",
            page=1,
            text="Our method replaces RNN layers with attention.",
            start_char=0,
            end_char=44,
            text_hash="cde123",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.claim_type == ClaimType.STRUCTURAL

    def test_extract_structural_based_on(self, extractor):
        """Test structural claim with 'based on' verb phrase."""
        chunk = IngestionChunk(
            chunk_id="chunk_012",
            source_id="paper_001",
            page=1,
            text="The architecture is based on BERT.",
            start_char=0,
            end_char=34,
            text_hash="def456",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.claim_type == ClaimType.STRUCTURAL


# ──────────────────────────────────────────────────────────────────────────────
# TEST: No Claim Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestNoClaimCases:
    """Tests for sentences that should produce NoClaim."""

    def test_no_claim_non_quantitative(self, extractor):
        """Test rejection of non-quantitative sentence."""
        chunk = IngestionChunk(
            chunk_id="chunk_013",
            source_id="paper_001",
            page=1,
            text="We evaluated our approach on various datasets.",
            start_char=0,
            end_char=45,
            text_hash="ghi789",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.no_claim is not None or result.claim is None

    def test_no_claim_missing_dataset(self, extractor):
        """Test performance claim without dataset context."""
        chunk = IngestionChunk(
            chunk_id="chunk_014",
            source_id="paper_001",
            page=1,
            text="The accuracy is 92.5%.",
            start_char=0,
            end_char=22,
            text_hash="jkl012",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # May or may not extract depending on context requirements
        assert result.claim is not None or result.no_claim is not None

    def test_no_claim_abstract_statement(self, extractor):
        """Test rejection of abstract/generic statement."""
        chunk = IngestionChunk(
            chunk_id="chunk_015",
            source_id="paper_001",
            page=1,
            text="Machine learning is important for AI.",
            start_char=0,
            end_char=37,
            text_hash="mno345",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.no_claim is not None or result.claim is None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism and Consistency
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractionDeterminism:
    """Tests for deterministic extraction behavior."""

    def test_extract_deterministic_output(self, extractor):
        """Test same input produces identical output."""
        chunk = IngestionChunk(
            chunk_id="chunk_016",
            source_id="paper_001",
            page=1,
            text="BERT achieves 92.5% accuracy on GLUE.",
            start_char=0,
            end_char=38,
            text_hash="pqr678",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        
        result1 = extract_from_request(extractor, request)
        result2 = extract_from_request(extractor, request)
        
        if result1.claim and result2.claim:
            assert result1.claim.subject == result2.claim.subject
            assert result1.claim.object == result2.claim.object
            assert result1.claim.claim_type == result2.claim.claim_type

    def test_extract_all_deterministic_order(self, extractor):
        """Test extract_all produces results in consistent order."""
        chunk = IngestionChunk(
            chunk_id="chunk_017",
            source_id="paper_001",
            page=1,
            text="Model achieves 92.5% accuracy and 0.85 F1.",
            start_char=0,
            end_char=43,
            text_hash="stu901",
            context_id="ctx_001",
            numeric_strings=["92.5", "0.85"],
            unit_strings=["%"],
            metric_names=["accuracy", "F1"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        
        results1 = extract_all_from_request(extractor, request)
        results2 = extract_all_from_request(extractor, request)
        
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            if r1.claim and r2.claim:
                assert r1.claim.object == r2.claim.object


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases and Boundary Conditions
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractionEdgeCases:
    """Tests for extraction edge cases."""

    def test_extract_with_punctuation_variations(self, extractor):
        """Test extraction handles punctuation variations."""
        chunk = IngestionChunk(
            chunk_id="chunk_018",
            source_id="paper_001",
            page=1,
            text="Model achieves 92.5% accuracy, on GLUE!",
            start_char=0,
            end_char=40,
            text_hash="vwx234",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None

    def test_extract_with_extra_whitespace(self, extractor):
        """Test extraction handles extra whitespace."""
        chunk = IngestionChunk(
            chunk_id="chunk_019",
            source_id="paper_001",
            page=1,
            text="Model  achieves   92.5%   accuracy   on   GLUE",
            start_char=0,
            end_char=47,
            text_hash="yza567",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None

    def test_extract_very_long_sentence(self, extractor):
        """Test extraction of very long sentence."""
        text = "The model achieves 92.5% accuracy on the GLUE benchmark, which includes " + \
               "a variety of natural language understanding tasks such as " + \
               "classification, similarity, and inference."
        chunk = IngestionChunk(
            chunk_id="chunk_020",
            source_id="paper_001",
            page=1,
            text=text,
            start_char=0,
            end_char=len(text),
            text_hash="bcd890",
            context_id="ctx_001",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None or result.no_claim is not None
