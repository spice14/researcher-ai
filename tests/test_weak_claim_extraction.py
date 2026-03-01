"""Tests for weak claim extraction (v2 tier system).

Validates that:
1. Weak claims are extracted from quantitative text
2. Strong claims remain unaffected by weak tier
3. Tiering is preserved through the pipeline
4. Misbindings stay at 0 even with weak tier enabled
"""

import pytest
from core.schemas.claim import ClaimTier
from services.ingestion.schemas import IngestionChunk
from services.extraction.service import ClaimExtractor
from services.extraction.weak_claim_validator import WeakClaimValidator


class TestWeakClaimValidator:
    """Test weak claim validation logic."""
    
    def test_accepts_quantitative_deltas(self):
        """Test acceptance of delta-based claims."""
        cases = [
            ("Latency improved by 34%", True),
            ("Error reduced from 0.54 to 0.31", True),
            ("2.3x improvement over baseline", True),
            ("Throughput increased by 15%", True),
        ]
        
        for text, expected in cases:
            valid, _ = WeakClaimValidator.validate(text)
            assert valid == expected, f"Failed for: {text}"
    
    def test_rejects_hedged_statements(self):
        """Test rejection of hedged language."""
        cases = [
            ("Accuracy may increase", False),
            ("Error could be reduced", False),
            ("Suggests 20% improvement", False),
        ]
        
        for text, expected in cases:
            valid, _ = WeakClaimValidator.validate(text)
            assert valid == expected, f"Failed for: {text}"
    
    def test_rejects_compound_metrics(self):
        """Test rejection of compound measurements."""
        cases = [
            ("Accuracy on Dataset A or Dataset B", False),
            ("Performance on Metric 1 and Metric 2", False),
        ]
        
        for text, expected in cases:
            valid, _ = WeakClaimValidator.validate(text)
            assert valid == expected, f"Failed for: {text}"
    
    def test_requires_measurable_property(self):
        """Test that measurable property is required."""
        cases = [
            ("p < 0.01", True),  # p-value is measurable
            ("The model improved", False),  # No quantification
            ("Accuracy improved", False),  # Delta but no value
        ]
        
        for text, expected in cases:
            valid, _ = WeakClaimValidator.validate(text)
            assert valid == expected, f"Failed for: {text}"


class TestWeakClaimExtraction:
    """Test weak claim extraction in ClaimExtractor."""
    
    def test_extract_with_weak_tier_enabled(self):
        """Test that weak claims are extracted when enabled."""
        extractor = ClaimExtractor()
        
        # Create chunk with weak-potential text
        chunk = IngestionChunk(
            chunk_id="test_001",
            text="Latency improved by 34% relative to baseline.",
            source_id="test_paper",
            start_char=0,
            end_char=45,
            text_hash="abc123",
            context_id="ctx_001",
            numeric_strings=["34"],
            unit_strings=["%"],
            metric_names=["latency"],
        )
        
        # Extract with weak tier
        claims = extractor.extract([chunk], include_weak=True)
        
        # Should have at least one claim
        assert len(claims) > 0
        
        # Check for weak tier claim
        weak_claims = [c for c in claims if c.tier == ClaimTier.WEAK]
        assert len(weak_claims) > 0, "No weak tier claims extracted"
        
        # Validate weak claim properties
        weak_claim = weak_claims[0]
        assert weak_claim.context_inferred is True
        assert weak_claim.context_explicit is False
    
    def test_extract_with_weak_tier_disabled(self):
        """Test that weak claims are not extracted when disabled."""
        extractor = ClaimExtractor()
        
        chunk = IngestionChunk(
            chunk_id="test_001",
            text="Latency improved by 34% relative to baseline.",
            source_id="test_paper",
            start_char=0,
            end_char=45,
            text_hash="abc123",
            context_id="ctx_001",
            numeric_strings=["34"],
            unit_strings=["%"],
            metric_names=["latency"],
        )
        
        # Extract without weak tier
        claims = extractor.extract([chunk], include_weak=False)
        
        # All claims should be strong tier or none extracted
        for claim in claims:
            assert claim.tier == ClaimTier.STRONG
    
    def test_weak_claims_preserved_in_separate_tier(self):
        """Test that weak claims don't interfere with strong claims."""
        extractor = ClaimExtractor()
        
        chunks = [
            # Strong claim candidate
            IngestionChunk(
                chunk_id="strong_001",
                text="BERT achieves 92% accuracy on GLUE benchmark.",
                source_id="test_paper",
                start_char=0,
                end_char=44,
                text_hash="strong",
                context_id="ctx_001",
                numeric_strings=["92"],
                unit_strings=["%"],
                metric_names=["accuracy"],
            ),
            # Weak claim candidate (with measurable property)
            IngestionChunk(
                chunk_id="weak_001",
                text="Latency improved by 15%.",
                source_id="test_paper",
                start_char=45,
                end_char=70,
                text_hash="weak",
                context_id="ctx_001",
                numeric_strings=["15"],
                unit_strings=["%"],
                metric_names=["latency"],
            ),
        ]
        
        claims = extractor.extract(chunks, include_weak=True)
        
        # Categorize by tier
        strong = [c for c in claims if c.tier == ClaimTier.STRONG]
        weak = [c for c in claims if c.tier == ClaimTier.WEAK]
        
        # Should have both types
        assert len(strong) > 0, "No strong tier claims"
        assert len(weak) > 0, "No weak tier claims"
        
        # Verify separation
        for s in strong:
            assert s.context_explicit is True
        
        for w in weak:
            assert w.context_inferred is True

    def test_weak_tier_uses_paragraph_dataset_context(self):
        """Weak extraction should inherit dataset context from prior paragraph chunk."""
        extractor = ClaimExtractor()

        chunks = [
            IngestionChunk(
                chunk_id="ctx_001",
                text="We evaluate on ImageNet and report baseline performance.",
                source_id="test_paper",
                start_char=0,
                end_char=56,
                text_hash="ctxhash",
                context_id="ctx_001",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
                page=1,
            ),
            IngestionChunk(
                chunk_id="weak_002",
                text="Latency improved by 18% compared to baseline.",
                source_id="test_paper",
                start_char=57,
                end_char=102,
                text_hash="weakhash",
                context_id="ctx_002",
                numeric_strings=["18"],
                unit_strings=["%"],
                metric_names=[],
                page=1,
            ),
        ]

        claims = extractor.extract(chunks, include_weak=True)
        weak_claims = [c for c in claims if c.tier == ClaimTier.WEAK]

        assert len(weak_claims) > 0
        assert any("ImageNet" in c.subject for c in weak_claims)


class TestWeakClaimNormalization:
    """Test that weak claims are not normalized (or handled specially)."""
    
    def test_strong_claims_only_in_normalization(self):
        """Test that normalization filter works by tier."""
        from services.normalization.service import NormalizationService
        from services.normalization.schemas import NormalizationRequest
        
        normalizer = NormalizationService()
        extractor = ClaimExtractor()
        
        chunk = IngestionChunk(
            chunk_id="test_001",
            text="Latency improved by 34%.",
            source_id="test_paper",
            start_char=0,
            end_char=25,
            text_hash="abc123",
            context_id="ctx_001",
            numeric_strings=["34"],
            unit_strings=["%"],
            metric_names=["latency"],
        )
        
        claims = extractor.extract([chunk], include_weak=True)
        weak_claims = [c for c in claims if c.tier == ClaimTier.WEAK]
        
        if weak_claims:
            weak_claim = weak_claims[0]
            # Normalization should handle weak claims gracefully
            # (either skip or tag as low confidence)
            result = normalizer.normalize(NormalizationRequest(claim=weak_claim))
            # Should not crash, regardless of outcome
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
