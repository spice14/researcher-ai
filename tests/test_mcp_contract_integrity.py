"""MCP contract integrity tests for canonical service interfaces."""

from services.belief.service import BeliefEngine
from services.contradiction.relation_engine import EpistemicRelationEngine
from services.extraction.service import ClaimExtractor
from services.extraction.tool import ExtractionTool
from services.ingestion.service import IngestionService
from services.normalization.service import NormalizationService


def test_service_contracts():
    extractor = ClaimExtractor()

    assert hasattr(IngestionService(), "ingest_text")
    assert hasattr(extractor, "extract")
    assert not hasattr(extractor, "extract_claims")
    assert not hasattr(extractor, "extract_all")
    assert hasattr(NormalizationService(), "normalize")
    assert hasattr(BeliefEngine(), "compute_beliefs")
    assert hasattr(EpistemicRelationEngine(), "analyze")


def test_extraction_tool_calls_extract(monkeypatch):
    tool = ExtractionTool()
    calls = {"count": 0}

    def fake_extract(chunks):
        calls["count"] += 1
        assert isinstance(chunks, list)
        return []

    monkeypatch.setattr(tool._service, "extract", fake_extract)

    payload = {
        "source_id": "paper_001",
        "chunks": [
            {
                "chunk_id": "chunk_001",
                "text": "The model achieves 92% accuracy.",
                "source_id": "paper_001",
            }
        ],
    }

    result = tool.call(payload)

    assert calls["count"] == 1
    assert result["source_id"] == "paper_001"
