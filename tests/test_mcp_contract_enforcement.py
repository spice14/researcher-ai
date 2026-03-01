"""MCP contract enforcement tests.

Validates that all service classes expose ONLY their canonical public methods
and that MCP tool wrappers call the correct methods.

This test prevents contract drift by asserting:
1. Canonical method EXISTS on service
2. Legacy/alias methods DO NOT exist
3. Tool wrapper calls canonical method
"""

import pytest
from services.ingestion.pdf_service import PDFIngestionService
from services.extraction.service import ClaimExtractor
from services.normalization.service import NormalizationService
from services.belief.service import BeliefEngine
from services.contradiction.relation_engine import EpistemicRelationEngine


class TestServiceContractEnforcement:
    """Validate canonical service interfaces."""

    def test_ingestion_service_contract(self):
        """PDFIngestionService must expose only ingest_pdf()."""
        service = PDFIngestionService()
        
        # Canonical method MUST exist
        assert hasattr(service, "ingest_pdf")
        assert callable(service.ingest_pdf)
        
        # Legacy aliases MUST NOT exist
        assert not hasattr(service, "ingest")
        assert not hasattr(service, "ingest_text")
        assert not hasattr(service, "process_pdf")

    def test_extraction_service_contract(self):
        """ClaimExtractor must expose only extract()."""
        service = ClaimExtractor()
        
        # Canonical method MUST exist
        assert hasattr(service, "extract")
        assert callable(service.extract)
        
        # Legacy aliases MUST NOT exist
        assert not hasattr(service, "extract_claims")
        assert not hasattr(service, "extract_all")  # This is intentionally private
        assert not hasattr(service, "process")
        assert not hasattr(service, "run")

    def test_normalization_service_contract(self):
        """NormalizationService must expose only normalize()."""
        service = NormalizationService()
        
        # Canonical method MUST exist
        assert hasattr(service, "normalize")
        assert callable(service.normalize)
        
        # Legacy aliases MUST NOT exist
        assert not hasattr(service, "normalize_claim")
        assert not hasattr(service, "process")

    def test_belief_engine_contract(self):
        """BeliefEngine must expose only compute_beliefs()."""
        service = BeliefEngine()
        
        # Canonical method MUST exist
        assert hasattr(service, "compute_beliefs")
        assert callable(service.compute_beliefs)
        
        # Legacy aliases MUST NOT exist
        assert not hasattr(service, "compute")
        assert not hasattr(service, "synthesize")

    def test_relation_engine_contract(self):
        """EpistemicRelationEngine must expose only analyze()."""
        service = EpistemicRelationEngine()
        
        # Canonical method MUST exist
        assert hasattr(service, "analyze")
        assert callable(service.analyze)
        
        # Legacy aliases MUST NOT exist
        assert not hasattr(service, "detect")
        assert not hasattr(service, "find_relations")


class TestToolWrapperContractEnforcement:
    """Validate that MCP tools call correct service methods."""

    def test_extraction_tool_calls_extract(self, monkeypatch):
        """ExtractionTool must call service.extract(), not extract_claims()."""
        from services.extraction.tool import ExtractionTool
        
        tool = ExtractionTool()
        calls = {"extract": 0, "extract_claims": 0}

        def fake_extract(chunks):
            calls["extract"] += 1
            return []

        monkeypatch.setattr(tool._service, "extract", fake_extract)

        # Ensure extract_claims doesn't exist (would raise AttributeError if called)
        assert not hasattr(tool._service, "extract_claims")

        payload = {
            "source_id": "test_paper",
            "chunks": [{
                "chunk_id": "chunk_001",
                "text": "BERT achieves 92%% accuracy.",
                "source_id": "test_paper",
            }],
        }

        result = tool.call(payload)

        assert calls["extract"] == 1
        assert result["source_id"] == "test_paper"


class TestE2EMethodResolution:
    """End-to-end tests ensuring method resolution works across full pipeline."""

    def test_extraction_pipeline_method_resolution(self, tmp_path):
        """Verify ClaimExtractor.extract() is callable in pipeline context."""
        from services.ingestion.schemas import IngestionChunk
        
        service = ClaimExtractor()
        
        # Create valid chunk
        chunk = IngestionChunk(
            chunk_id="test_001",
            text="The model achieves 92% accuracy on ImageNet.",
            source_id="test_paper",
            start_char=0,
            end_char=48,
            text_hash="abc123",
            context_id="ctx_imagenet",
            numeric_strings=["92"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        )
        
        # Call canonical method - MUST NOT raise AttributeError
        claims = service.extract([chunk])
        
        # Validate result is list
        assert isinstance(claims, list)

    def test_normalization_pipeline_method_resolution(self):
        """Verify NormalizationService.normalize() is callable in pipeline context."""
        service = NormalizationService()
        
        # Verify canonical method exists
        assert hasattr(service, "normalize")
        assert callable(service.normalize)
        
        # Contract enforcement: method is accessible via MCP interface
        # (Full integration tested in test_brutal_100_e2e.py)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
