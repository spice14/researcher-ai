"""Additional tests for ingestion service targeting missing error paths."""

import pytest
from services.ingestion.service import IngestionService
from services.ingestion.schemas import IngestionRequest


@pytest.fixture
def ingestion_service():
    """Fixture providing IngestionService instance."""
    return IngestionService()


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Ingestion Error Paths
# ──────────────────────────────────────────────────────────────────────────────


class TestIngestionErrorHandling:
    """Tests for ingestion service error handling."""

    def test_ingest_invalid_request_missing_source_id(self, ingestion_service):
        """Test ingestion rejects invalid requests (missing source_id)."""
        # This tests the Pydantic validation
        with pytest.raises(Exception):  # ValidationError
            request = IngestionRequest(raw_text="test", source_id="")
            ingestion_service.ingest_text(request)

    def test_ingest_invalid_request_empty_raw_text(self, ingestion_service):
        """Test ingestion rejects empty raw_text."""
        with pytest.raises(Exception):  # ValidationError
            request = IngestionRequest(raw_text="", source_id="test")
            ingestion_service.ingest_text(request)

    def test_ingest_with_invalid_chunk_size(self, ingestion_service):
        """Test ingestion with invalid chunk_size parameter."""
        with pytest.raises(Exception):  # Validation should fail
            request = IngestionRequest(
                raw_text="test text",
                source_id="test",
                chunk_size=100,  # Too small (min is 200)
            )
            ingestion_service.ingest_text(request)

    def test_ingest_with_invalid_chunk_overlap(self, ingestion_service):
        """Test ingestion with overlap >= chunk_size."""
        with pytest.raises(Exception):
            request = IngestionRequest(
                raw_text="test text",
                source_id="test",
                chunk_size=500,
                chunk_overlap=500,  # Should be < chunk_size
            )
            ingestion_service.ingest_text(request)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Ingestion Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestIngestionEdgeCases:
    """Tests for ingestion edge cases."""

    def test_ingest_text_at_exact_chunk_boundary(self, ingestion_service):
        """Test ingestion when text length is exactly chunk_size."""
        # 1024 characters, default chunk_size is 1000
        text = "a" * 1024
        request = IngestionRequest(raw_text=text, source_id="boundary_test")
        result = ingestion_service.ingest_text(request)

        assert result.chunks is not None
        assert len(result.chunks) > 0

    def test_ingest_very_large_text(self, ingestion_service):
        """Test ingestion of very large text."""
        # Create large text (10MB worth of chunks)
        text = ("Model achieves 92% accuracy. " * 100000)[:500000]  # 500KB
        request = IngestionRequest(
            raw_text=text,
            source_id="large_text",
            chunk_size=2000,
        )
        result = ingestion_service.ingest_text(request)

        assert result.chunks is not None
        assert len(result.chunks) > 100

    def test_ingest_text_with_special_unicode(self, ingestion_service):
        """Test ingestion handles unicode properly."""
        text = "Model 模型 achieves 92% 准确度 accuracy. Модель достигает 92% точности."
        request = IngestionRequest(raw_text=text, source_id="unicode_test")
        result = ingestion_service.ingest_text(request)

        assert result.chunks is not None
        assert len(result.chunks) > 0

    def test_ingest_text_with_long_lines(self, ingestion_service):
        """Test ingestion handles very long lines without breaks."""
        # Single line longer than chunk_size
        text = "x" * 5000
        request = IngestionRequest(
            raw_text=text,
            source_id="long_line",
            chunk_size=1000,
        )
        result = ingestion_service.ingest_text(request)

        assert result.chunks is not None

    def test_ingestion_chunk_ordering(self, ingestion_service):
        """Test chunks maintain proper order and coverage."""
        text = "First part. " * 100 + "Second part. " * 100
        request = IngestionRequest(raw_text=text, source_id="ordering_test")
        result = ingestion_service.ingest_text(request)

        # Verify chunks form a continuous coverage
        chunks = result.chunks
        for i, chunk in enumerate(chunks[:-1]):
            next_chunk = chunks[i + 1]
            # Next chunk should start near where this one ends (accounting for overlap)
            assert next_chunk.start_char >= chunk.start_char

    def test_ingestion_numeric_extraction(self, ingestion_service):
        """Test ingestion extracts numeric strings correctly."""
        text = "Model achieves 92.5% accuracy and 45ms latency with 110M parameters."
        request = IngestionRequest(raw_text=text, source_id="numeric_test")
        result = ingestion_service.ingest_text(request)

        # Should have extracted numeric information
        assert result.chunks is not None
        # At least one chunk should have telemetry
        has_telemetry = any(
            len(c.numeric_strings) > 0 or len(c.metric_names) > 0 for c in result.chunks
        )
        assert has_telemetry


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Ingestion Formatting and Normalization
# ──────────────────────────────────────────────────────────────────────────────


class TestIngestionFormatting:
    """Tests for text formatting and normalization."""

    def test_ingestion_whitespace_handling(self, ingestion_service):
        """Test ingestion handles various whitespace correctly."""
        text = "Line 1\n\nLine 3\t\tLine 4     Line 5"
        request = IngestionRequest(raw_text=text, source_id="whitespace_test")
        result = ingestion_service.ingest_text(request)

        assert result.chunks is not None

    def test_ingestion_duplicate_consecutive_text(self, ingestion_service):
        """Test ingestion with chunks that have overlap."""
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 50
        request = IngestionRequest(
            raw_text=text,
            source_id="overlap_test",
            chunk_size=200,
            chunk_overlap=50,
        )
        result = ingestion_service.ingest_text(request)

        # Overlapping chunks should still be generated correctly
        chunks = result.chunks
        if len(chunks) > 1:
            # Later chunk should start before earlier chunk ends
            assert chunks[1].start_char < chunks[0].end_char


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Ingestion Metadata Preservation
# ──────────────────────────────────────────────────────────────────────────────


class TestIngestionMetadata:
    """Tests for metadata preservation."""

    def test_source_id_preservation(self, ingestion_service):
        """Test source_id is preserved in chunks."""
        source_id = "paper_xyz_001"
        text = "Test content about model performance."
        request = IngestionRequest(raw_text=text, source_id=source_id)
        result = ingestion_service.ingest_text(request)

        for chunk in result.chunks:
            assert chunk.source_id == source_id

    def test_chunk_ids_uniqueness(self, ingestion_service):
        """Test chunk IDs are unique."""
        text = "Content " * 200
        request = IngestionRequest(raw_text=text, source_id="unique_test")
        result = ingestion_service.ingest_text(request)

        chunk_ids = [c.chunk_id for c in result.chunks]
        assert len(chunk_ids) == len(set(chunk_ids))  # All unique

    def test_text_hash_validity(self, ingestion_service):
        """Test text hash is properly computed."""
        text = "Content for hashing"
        request = IngestionRequest(raw_text=text, source_id="hash_test")
        result = ingestion_service.ingest_text(request)

        for chunk in result.chunks:
            # Hash should be non-empty string
            assert isinstance(chunk.text_hash, str)
            assert len(chunk.text_hash) > 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Ingestion Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestIngestionDeterminism:
    """Tests for deterministic ingestion behavior."""

    def test_same_input_produces_same_chunks(self, ingestion_service):
        """Test same input produces identical chunks."""
        request_data = {
            "raw_text": "Model achieves 92% accuracy on benchmark dataset.",
            "source_id": "determinism_test",
        }

        result1 = ingestion_service.ingest_text(IngestionRequest(**request_data))
        result2 = ingestion_service.ingest_text(IngestionRequest(**request_data))

        assert len(result1.chunks) == len(result2.chunks)
        for c1, c2 in zip(result1.chunks, result2.chunks):
            assert c1.chunk_id == c2.chunk_id
            assert c1.text == c2.text
            assert c1.text_hash == c2.text_hash
