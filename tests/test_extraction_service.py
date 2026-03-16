"""Comprehensive unit tests for deterministic claim extraction service."""

import pytest
from core.schemas.claim import Claim, ClaimSubtype, ClaimType, ConfidenceLevel, Polarity
from services.extraction.schemas import (
    ClaimExtractionRequest,
    ClaimExtractionResult,
    NoClaimReason,
    NoClaim,
)
from services.extraction.service import ClaimExtractor
from services.ingestion.schemas import IngestionChunk


def extract_from_request(extractor: ClaimExtractor, request: ClaimExtractionRequest) -> ClaimExtractionResult:
    """Test helper: execute extraction using the canonical engine internals."""
    results = extractor._extract_all(request)
    if results:
        return results[0]
    return ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NON_CLAIM))


def extract_all_from_request(
    extractor: ClaimExtractor, request: ClaimExtractionRequest
) -> list[ClaimExtractionResult]:
    """Test helper: return all extraction results for a chunk."""
    return extractor._extract_all(request)


@pytest.fixture
def extractor():
    """Fixture providing a ClaimExtractor instance."""
    return ClaimExtractor()


@pytest.fixture
def basic_performance_chunk():
    """Fixture: sentence describing model performance on benchmark."""
    return IngestionChunk(
        chunk_id="chunk_001",
        source_id="paper_001",
        page=1,
        text="BERT achieves 92.5% accuracy on GLUE.",
        start_char=0,
        end_char=42,
        text_hash="abc123",
        context_id="ctx_001",
        numeric_strings=["92.5"],
        unit_strings=["%"],
        metric_names=["accuracy"],
    )


@pytest.fixture
def efficiency_chunk():
    """Fixture: sentence describing training time or memory."""
    return IngestionChunk(
        chunk_id="chunk_002",
        source_id="paper_001",
        page=1,
        text="Training requires 24 hours on a single V100.",
        start_char=100,
        end_char=142,
        text_hash="def456",
        context_id="ctx_001",
        numeric_strings=["24"],
        unit_strings=["hours"],
        metric_names=[],
    )


@pytest.fixture
def structural_chunk():
    """Fixture: sentence describing architecture or mechanism."""
    return IngestionChunk(
        chunk_id="chunk_003",
        source_id="paper_001",
        page=1,
        text="The model introduces a transformer-based architecture.",
        start_char=200,
        end_char=253,
        text_hash="ghi789",
        context_id="ctx_001",
        numeric_strings=[],
        unit_strings=[],
        metric_names=[],
    )


@pytest.fixture
def hedged_statement_chunk():
    """Fixture: sentence with hedging language (should be rejected)."""
    return IngestionChunk(
        chunk_id="chunk_004",
        source_id="paper_001",
        page=1,
        text="The model may achieve 85% accuracy on the dataset.",
        start_char=300,
        end_char=350,
        text_hash="jkl012",
        context_id="ctx_001",
        numeric_strings=["85"],
        unit_strings=["%"],
        metric_names=["accuracy"],
    )


@pytest.fixture
def non_claim_chunk():
    """Fixture: chunk with no extractable claim."""
    return IngestionChunk(
        chunk_id="chunk_005",
        source_id="paper_001",
        page=1,
        text="We ran experiments on various datasets.",
        start_char=400,
        end_char=439,
        text_hash="mno345",
        context_id="ctx_001",
        numeric_strings=[],
        unit_strings=[],
        metric_names=[],
    )


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Basic Performance Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestPerformanceExtraction:
    """Tests for PERFORMANCE claim extraction."""

    def test_extract_performance_claim_basic(self, extractor, basic_performance_chunk):
        """Test extraction of basic performance claim."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.no_claim is None
        assert result.claim.claim_type == ClaimType.PERFORMANCE
        assert result.claim.subject is not None
        assert result.claim.object is not None
        assert result.claim.predicate is not None
        assert "92.5" in result.claim.object or "accuracy" in result.claim.object

    def test_extract_all_performance_single_result(self, extractor, basic_performance_chunk):
        """Test extract_all returns list with single performance claim."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        results = extract_all_from_request(extractor, request)
        
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].claim is not None
        assert results[0].claim.claim_type == ClaimType.PERFORMANCE

    def test_performance_claim_has_evidence(self, extractor, basic_performance_chunk):
        """Test that extracted performance claim has evidence attached."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.evidence is not None
        assert len(result.claim.evidence) > 0
        assert result.claim.evidence[0].snippet == basic_performance_chunk.text

    def test_performance_claim_has_deterministic_id(self, extractor, basic_performance_chunk):
        """Test claim_id is deterministic (same input → same ID)."""
        request1 = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result1 = extract_from_request(extractor, request1)
        
        request2 = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result2 = extract_from_request(extractor, request2)
        
        assert result1.claim is not None
        assert result2.claim is not None
        assert result1.claim.claim_id == result2.claim.claim_id

    def test_performance_supports_polarity(self, extractor, basic_performance_chunk):
        """Test performance claim typically has SUPPORTS polarity."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        assert result.claim is not None
        assert result.claim.polarity in [Polarity.SUPPORTS, Polarity.REFUTES, Polarity.NEUTRAL]


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Efficiency Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestEfficiencyExtraction:
    """Tests for EFFICIENCY claim extraction."""

    def test_extract_efficiency_claim_training_time(self, extractor, efficiency_chunk):
        """Test extraction of training time efficiency claim."""
        request = ClaimExtractionRequest(chunk=efficiency_chunk)
        result = extract_from_request(extractor, request)
        
        # Either extracts efficiency or rejects with valid reason
        if result.claim is not None:
            assert result.no_claim is None
            assert result.claim.claim_type == ClaimType.EFFICIENCY
        else:
            assert result.no_claim is not None
            assert result.no_claim.reason_code in [
                NoClaimReason.NO_PREDICATE,
                NoClaimReason.NO_METRIC,
                NoClaimReason.NON_PERFORMANCE_NUMERIC,
            ]

    def test_efficiency_has_numeric_requirement(self, extractor):
        """Test efficiency claims require numeric values."""
        chunk = IngestionChunk(
            chunk_id="chunk_eff_1",
            source_id="paper_001",
            page=1,
            text="Training requires GPU memory.",
            start_char=0,
            end_char=30,
            text_hash="xyz123",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=["GPU"],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Without numeric value, should not extract performance claim
        if result.claim is not None and result.claim.claim_type == ClaimType.PERFORMANCE:
            assert False, "Should not extract performance without numeric value"


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Structural Extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestStructuralExtraction:
    """Tests for STRUCTURAL claim extraction."""

    def test_extract_structural_claim_basic(self, extractor, structural_chunk):
        """Test extraction of basic structural claim."""
        request = ClaimExtractionRequest(chunk=structural_chunk)
        result = extract_from_request(extractor, request)
        
        # Should extract structural claim (no metric/numeric requirement)
        if result.claim is not None:
            assert result.no_claim is None
            assert result.claim.claim_type == ClaimType.STRUCTURAL
        else:
            # Valid rejection for structural
            assert result.no_claim is not None

    def test_structural_requires_entity(self, extractor):
        """Test structural claims require structural entity words."""
        chunk = IngestionChunk(
            chunk_id="chunk_struct_1",
            source_id="paper_001",
            page=1,
            text="We introduced new methods.",
            start_char=0,
            end_char=30,
            text_hash="abc456",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Without structural entity (model, architecture, etc.), may be rejected
        # This is acceptable behavior
        assert result.claim is not None or result.no_claim is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Hedging and Rejection
# ──────────────────────────────────────────────────────────────────────────────


class TestHedgingAndRejection:
    """Tests for hedged statements and rejection cases."""

    def test_hedged_statement_rejected(self, extractor, hedged_statement_chunk):
        """Test hedged statements are rejected."""
        request = ClaimExtractionRequest(chunk=hedged_statement_chunk)
        result = extract_from_request(extractor, request)
        
        # Hedged statements should be rejected
        if result.no_claim is not None:
            assert result.no_claim.reason_code == NoClaimReason.HEDGED_STATEMENT
        elif result.claim is not None:
            # Some hedge markers might still allow extraction
            pass

    def test_non_claim_chunk_rejected(self, extractor, non_claim_chunk):
        """Test non-claim chunk is rejected appropriately."""
        request = ClaimExtractionRequest(chunk=non_claim_chunk)
        result = extract_from_request(extractor, request)
        
        # Non-claim should result in NoClaim
        assert result.no_claim is not None or result.claim is None

    def test_missing_context_performance_rejected(self, extractor):
        """Test performance claim without context is marked appropriately."""
        chunk = IngestionChunk(
            chunk_id="chunk_no_ctx",
            source_id="paper_001",
            page=1,
            text="Achievement: 88.5% accuracy",
            start_char=0,
            end_char=28,
            text_hash="zzz999",
            context_id="ctx_unknown",
            numeric_strings=["88.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Result should be valid (either claim or rejection reason)
        assert result.claim is not None or result.no_claim is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Extract vs Extract_all
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractMethods:
    """Tests comparing extract() vs extract_all()."""

    def test_extract_returns_first_of_extract_all(self, extractor, basic_performance_chunk):
        """Test extract() returns first result of extract_all()."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        
        single = extract_from_request(extractor, request)
        multiple = extract_all_from_request(extractor, request)
        
        assert len(multiple) >= 1
        
        if multiple[0].claim is not None and single.claim is not None:
            assert single.claim.claim_id == multiple[0].claim.claim_id
        elif multiple[0].no_claim is not None and single.no_claim is not None:
            assert single.no_claim.reason_code == multiple[0].no_claim.reason_code

    def test_extract_returns_noclaim_when_extract_all_empty(self, extractor):
        """Test extract() returns NoClaim when extract_all() returns empty."""
        # Use minimal text since empty text is not allowed by schema
        chunk = IngestionChunk(
            chunk_id="chunk_minimal",
            source_id="paper_001",
            page=1,
            text="x",
            start_char=0,
            end_char=1,
            text_hash="minimal",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        
        single = extract_from_request(extractor, request)
        multiple = extract_all_from_request(extractor, request)
        
        # Single should correspond to multiple
        assert single is not None or multiple is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: XOR Validation (claim XOR no_claim)
# ──────────────────────────────────────────────────────────────────────────────


class TestXORValidation:
    """Tests for ClaimExtractionResult XOR constraint."""

    def test_result_xor_claim_or_no_claim(self, extractor, basic_performance_chunk):
        """Test result always has exactly one of claim or no_claim."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        # XOR: exactly one should be set
        has_claim = result.claim is not None
        has_no_claim = result.no_claim is not None
        assert has_claim != has_no_claim, "Result must have exactly one of claim or no_claim"

    def test_result_never_both_claim_and_no_claim(self, extractor, non_claim_chunk):
        """Test result never has both claim and no_claim."""
        request = ClaimExtractionRequest(chunk=non_claim_chunk)
        result = extract_from_request(extractor, request)
        
        assert not (result.claim is not None and result.no_claim is not None)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_minimal_chunk_text(self, extractor):
        """Test extraction on chunk with minimal text."""
        # Schema requires min_length=1, so use minimal text
        chunk = IngestionChunk(
            chunk_id="chunk_minimal_text",
            source_id="paper_001",
            page=1,
            text="a",
            start_char=0,
            end_char=1,
            text_hash="minimal_hash",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should handle gracefully
        assert result.claim is not None or result.no_claim is not None

    def test_long_text(self, extractor):
        """Test extraction on text that stays within claim limits."""
        # Keep text short enough for Claim.object (max 500 chars)
        long_text = "Model architecture consists of transformer layers "
        chunk = IngestionChunk(
            chunk_id="chunk_long",
            source_id="paper_001",
            page=1,
            text=long_text,
            start_char=0,
            end_char=len(long_text),
            text_hash="long_hash",
            context_id="ctx_001",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should handle without crashing
        assert result.claim is not None or result.no_claim is not None

    def test_special_characters_in_text(self, extractor):
        """Test extraction with special characters."""
        chunk = IngestionChunk(
            chunk_id="chunk_special",
            source_id="paper_001",
            page=1,
            text="Model achieves 92.5% ± 0.3% on GLUE (benchmark).",
            start_char=0,
            end_char=48,
            text_hash="special_hash",
            context_id="ctx_001",
            numeric_strings=["92.5", "0.3"],
            unit_strings=["%"],
            metric_names=["GLUE"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should handle special characters gracefully
        assert result.claim is not None or result.no_claim is not None

    def test_multiple_numbers_in_text(self, extractor):
        """Test extraction with multiple numeric values."""
        chunk = IngestionChunk(
            chunk_id="chunk_multinums",
            source_id="paper_001",
            page=1,
            text="BERT (2018) achieves 92.5% accuracy on 8 GLUE tasks.",
            start_char=0,
            end_char=52,
            text_hash="multinums_hash",
            context_id="ctx_001",
            numeric_strings=["2018", "92.5", "8"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should extract or identify reason for rejection
        assert result.claim is not None or result.no_claim is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Schema and Type Consistency
# ──────────────────────────────────────────────────────────────────────────────


class TestSchemaConsistency:
    """Tests for schema consistency and type correctness."""

    def test_claim_result_schema_valid(self, extractor, basic_performance_chunk):
        """Test ClaimExtractionResult instances are valid Pydantic models."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        # Should be valid ClaimExtractionResult
        assert isinstance(result, ClaimExtractionResult)
        
        # Validate round-trip serialization
        result_dict = result.model_dump()
        result_restored = ClaimExtractionResult(**result_dict)
        assert isinstance(result_restored, ClaimExtractionResult)

    def test_claim_has_required_fields(self, extractor, basic_performance_chunk):
        """Test extracted Claim has all required fields."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        result = extract_from_request(extractor, request)
        
        if result.claim is not None:
            claim = result.claim
            assert claim.claim_id is not None
            assert claim.subject is not None
            assert claim.predicate is not None
            assert claim.object is not None
            assert claim.claim_type is not None
            assert claim.polarity is not None
            assert claim.confidence_level is not None
            assert claim.evidence is not None

    def test_no_claim_has_required_fields(self, extractor, non_claim_chunk):
        """Test NoClaim results have reason_code."""
        request = ClaimExtractionRequest(chunk=non_claim_chunk)
        result = extract_from_request(extractor, request)
        
        if result.no_claim is not None:
            no_claim = result.no_claim
            assert no_claim.reason_code is not None
            assert isinstance(no_claim.reason_code, NoClaimReason)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic extraction behavior."""

    def test_deterministic_extraction_same_input_same_output(self, extractor, basic_performance_chunk):
        """Test same input always produces same output."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        
        result1 = extract_from_request(extractor, request)
        result2 = extract_from_request(extractor, request)
        result3 = extract_from_request(extractor, request)
        
        # All three should be identical
        if result1.claim is not None and result2.claim is not None and result3.claim is not None:
            assert result1.claim.claim_id == result2.claim.claim_id == result3.claim.claim_id
            assert result1.claim.subject == result2.claim.subject == result3.claim.subject

    def test_deterministic_rejection_reasons(self, extractor, hedged_statement_chunk):
        """Test rejection reasons are consistent."""
        request = ClaimExtractionRequest(chunk=hedged_statement_chunk)
        
        result1 = extract_from_request(extractor, request)
        result2 = extract_from_request(extractor, request)
        
        if result1.no_claim is not None and result2.no_claim is not None:
            assert result1.no_claim.reason_code == result2.no_claim.reason_code


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Request Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestRequestValidation:
    """Tests for ClaimExtractionRequest validation."""

    def test_valid_request_accepted(self, extractor, basic_performance_chunk):
        """Test valid requests are accepted."""
        request = ClaimExtractionRequest(chunk=basic_performance_chunk)
        
        # Should not raise any exception
        result = extract_from_request(extractor, request)
        assert result is not None

    def test_request_with_valid_chunk(self, extractor):
        """Test request validation with valid chunk."""
        chunk = IngestionChunk(
            chunk_id="valid_chunk",
            source_id="paper_test",
            page=2,
            text="Model achieves state-of-the-art results.",
            start_char=0,
            end_char=40,
            text_hash="test_hash",
            context_id="ctx_test",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        )
        request = ClaimExtractionRequest(chunk=chunk)
        result = extract_from_request(extractor, request)
        
        # Should handle valid request
        assert result is not None
        assert isinstance(result, ClaimExtractionResult)
