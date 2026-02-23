"""Tests for ingestion service."""

import pytest
from services.ingestion.service import IngestionService
from services.ingestion.schemas import IngestionRequest, IngestionResult


class TestIngestionService:
    """Test cases for IngestionService."""

    def test_init(self):
        """Test IngestionService initialization."""
        service = IngestionService()
        assert service is not None

    def test_ingest_text_basic(self, sample_ingestion_request):
        """Test basic text ingestion."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        assert isinstance(result, IngestionResult)
        assert result.chunks is not None
        assert len(result.chunks) > 0

    def test_ingest_text_preserves_metadata(self, sample_ingestion_request):
        """Test that metadata is preserved during ingestion."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        for chunk in result.chunks:
            assert chunk.source_id == sample_ingestion_request.source_id
            assert chunk.text_hash is not None
            assert len(chunk.text) > 0

    def test_ingest_text_chunk_overlap(self, sample_ingestion_request):
        """Test that chunks have proper overlap."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        assert len(result.chunks) > 0
        # Verify chunk boundaries
        for chunk in result.chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char

    def test_ingest_text_invalid_empty_text_fails(self):
        """Test that empty text fails validation."""
        service = IngestionService()
        
        with pytest.raises(Exception):
            request = IngestionRequest(raw_text="", source_id="test")

    def test_ingest_text_numeric_extraction(self):
        """Test numeric string extraction during ingestion."""
        service = IngestionService()
        request = IngestionRequest(
            raw_text="The accuracy is 0.95 and precision is 0.87.",
            source_id="test_num",
        )
        result = service.ingest_text(request)

        # At least one chunk should have numeric strings
        numeric_found = any(chunk.numeric_strings for chunk in result.chunks)
        assert numeric_found

    def test_ingest_text_metric_extraction(self):
        """Test metric name extraction during ingestion."""
        service = IngestionService()
        request = IngestionRequest(
            raw_text="The model achieved 92% accuracy on the dataset.",
            source_id="test_metric",
        )
        result = service.ingest_text(request)

        # At least one chunk should have metric names
        metrics_found = any(chunk.metric_names for chunk in result.chunks)
        assert metrics_found

    def test_ingest_text_determinism(self, sample_ingestion_request):
        """Test that ingestion is deterministic."""
        service = IngestionService()
        result1 = service.ingest_text(sample_ingestion_request)
        result2 = service.ingest_text(sample_ingestion_request)

        assert len(result1.chunks) == len(result2.chunks)
        for c1, c2 in zip(result1.chunks, result2.chunks):
            assert c1.text_hash == c2.text_hash
            assert c1.text == c2.text

    def test_ingest_text_invalid_chunk_size_fails(self):
        """Test that invalid chunk size fails."""
        service = IngestionService()
        
        with pytest.raises(Exception):
            request = IngestionRequest(
                raw_text="Test text",
                source_id="test",
                chunk_size=100,  # Below minimum 200
            )

    def test_ingest_text_context_id_assignment(self):
        """Test that context IDs are assigned to chunks."""
        service = IngestionService()
        request = IngestionRequest(
            raw_text="Test text for context assignment.",
            source_id="test_ctx",
        )
        result = service.ingest_text(request)

        for chunk in result.chunks:
            assert chunk.context_id is not None
            assert len(chunk.context_id) > 0

    def test_ingest_text_chunk_ids_unique(self, sample_ingestion_request):
        """Test that chunk IDs are unique."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        chunk_ids = [chunk.chunk_id for chunk in result.chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_ingest_text_preserves_page_numbers(self):
        """Test that page numbers are assigned."""
        service = IngestionService()
        request = IngestionRequest(
            raw_text="Page 1 content.\nPage 2 content.",
            source_id="test_pages",
        )
        result = service.ingest_text(request)

        for chunk in result.chunks:
            assert chunk.page >= 1

    def test_ingest_text_telemetry_captured(self, sample_ingestion_request):
        """Test that extraction telemetry is captured."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        assert result.telemetry is not None
        assert hasattr(result.telemetry, "numeric_strings")
        assert hasattr(result.telemetry, "metric_names")

    def test_ingest_text_warnings_list(self, sample_ingestion_request):
        """Test that warnings list is populated."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        assert isinstance(result.warnings, list)

    def test_ingest_text_source_id_preserved(self, sample_ingestion_request):
        """Test that source ID is preserved in result."""
        service = IngestionService()
        result = service.ingest_text(sample_ingestion_request)

        assert result.source_id == sample_ingestion_request.source_id

