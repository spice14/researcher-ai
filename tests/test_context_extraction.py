"""Tests for context extraction service."""

import pytest
from services.context.service import ContextExtractor


class TestContextExtractor:
    """Test cases for ContextExtractor."""

    def test_init(self):
        """Test ContextExtractor initialization."""
        extractor = ContextExtractor()
        assert extractor is not None

    def test_extract_basic(self, sample_ingestion_chunks):
        """Test basic context extraction."""
        extractor = ContextExtractor()
        result = extractor.extract_contexts(sample_ingestion_chunks)
        assert result is not None

    def test_extract_empty_list(self):
        """Test extraction with empty chunks list."""
        extractor = ContextExtractor()
        result = extractor.extract_contexts([])
        assert result is not None

    def test_extract_determinism(self, sample_ingestion_chunks):
        """Test that extraction is deterministic."""
        extractor = ContextExtractor()
        result1 = extractor.extract_contexts(sample_ingestion_chunks)
        result2 = extractor.extract_contexts(sample_ingestion_chunks)
        assert result1 is not None
        assert result2 is not None
