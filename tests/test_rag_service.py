"""Comprehensive unit tests for deterministic RAG retrieval service."""

import pytest
from services.rag.service import RAGService
from services.rag.schemas import QueryRequest, RAGResult, RAGMatch
from services.ingestion.schemas import IngestionChunk


@pytest.fixture
def rag_service():
    """Fixture providing a RAGService instance."""
    return RAGService()


@pytest.fixture
def sample_corpus():
    """Fixture: sample corpus of chunks for retrieval."""
    return [
        IngestionChunk(
            chunk_id="chunk_1",
            source_id="paper_001",
            page=1,
            text="BERT achieves 92.5% accuracy on GLUE benchmark.",
            start_char=0,
            end_char=48,
            text_hash="hash_1",
            context_id="ctx_1",
            numeric_strings=["92.5"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        ),
        IngestionChunk(
            chunk_id="chunk_2",
            source_id="paper_001",
            page=2,
            text="GPT-2 language model shows impressive zero-shot performance.",
            start_char=100,
            end_char=158,
            text_hash="hash_2",
            context_id="ctx_1",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        ),
        IngestionChunk(
            chunk_id="chunk_3",
            source_id="paper_002",
            page=1,
            text="Transformer architecture uses self-attention mechanisms.",
            start_char=0,
            end_char=54,
            text_hash="hash_3",
            context_id="ctx_2",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        ),
        IngestionChunk(
            chunk_id="chunk_4",
            source_id="paper_002",
            page=2,
            text="Attention is all you need for machine translation.",
            start_char=100,
            end_char=150,
            text_hash="hash_4",
            context_id="ctx_2",
            numeric_strings=[],
            unit_strings=[],
            metric_names=[],
        ),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Basic Retrieval
# ──────────────────────────────────────────────────────────────────────────────


class TestBasicRetrieval:
    """Tests for basic RAG retrieval."""

    def test_retrieve_returns_result(self, rag_service, sample_corpus):
        """Test retrieve returns RAGResult."""
        request = QueryRequest(
            query="BERT accuracy",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        assert isinstance(result, RAGResult)
        assert result.query == "BERT accuracy"
        assert result.retrieval_method is not None
        assert result.matches is not None
        assert isinstance(result.matches, list)

    def test_retrieve_single_match(self, rag_service):
        """Test retrieval with single relevant chunk."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT model achieves 92.5% accuracy.",
                start_char=0,
                end_char=35,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=["92.5"],
                unit_strings=["%"],
                metric_names=["accuracy"],
            ),
        ]

        request = QueryRequest(
            query="BERT accuracy",
            top_k=5,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        assert len(result.matches) > 0
        assert result.matches[0].chunk_id == "chunk_1"

    def test_retrieve_empty_corpus(self, rag_service):
        """Test retrieval with empty corpus."""
        request = QueryRequest(
            query="test query",
            top_k=5,
            corpus=[],
        )
        result = rag_service.retrieve(request)

        assert len(result.matches) == 0
        assert len(result.warnings) > 0

    def test_retrieve_no_matches(self, rag_service, sample_corpus):
        """Test retrieval with no matching documents."""
        request = QueryRequest(
            query="zzzzzzzzz xyzxyzxyz qqqqqqqqqq",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        # Should return empty matches list
        assert len(result.matches) == 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Match Ranking
# ──────────────────────────────────────────────────────────────────────────────


class TestMatchRanking:
    """Tests for match ranking and scoring."""

    def test_matches_ranked_by_score(self, rag_service, sample_corpus):
        """Test matches are ranked by descending score."""
        request = QueryRequest(
            query="BERT accuracy",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        # Verify ranking order (descending scores)
        for i in range(len(result.matches) - 1):
            assert result.matches[i].score >= result.matches[i + 1].score

    def test_highest_scoring_match_first(self, rag_service):
        """Test highest scoring match appears first."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_low_relevance",
                source_id="paper_001",
                page=1,
                text="The quick brown fox jumps.",
                start_char=0,
                end_char=27,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
            IngestionChunk(
                chunk_id="chunk_high_relevance",
                source_id="paper_001",
                page=2,
                text="BERT achieves accuracy on benchmark.",
                start_char=50,
                end_char=87,
                text_hash="hash_2",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request = QueryRequest(
            query="BERT accuracy benchmark",
            top_k=5,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        # Highest relevance should be first
        if len(result.matches) > 1:
            assert result.matches[0].score >= result.matches[1].score

    def test_score_range(self, rag_service, sample_corpus):
        """Test match scores are in valid range."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        for match in result.matches:
            assert match.score >= 0.0
            assert match.score <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Top-K Limiting
# ──────────────────────────────────────────────────────────────────────────────


class TestTopKLimiting:
    """Tests for top-k result limiting."""

    def test_top_k_respected(self, rag_service):
        """Test top_k parameter limits results."""
        corpus = [
            IngestionChunk(
                chunk_id=f"chunk_{i}",
                source_id="paper_001",
                page=1,
                text=f"BERT model variant {i}",
                start_char=i,
                end_char=i + 20,
                text_hash=f"hash_{i}",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            )
            for i in range(20)
        ]

        request = QueryRequest(
            query="BERT",
            top_k=3,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        assert len(result.matches) <= 3

    def test_fewer_results_than_top_k(self, rag_service):
        """Test result count when fewer matches than top_k."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT accuracy",
                start_char=0,
                end_char=13,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request = QueryRequest(
            query="BERT",
            top_k=10,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        # Should return 1 result, not 10
        assert len(result.matches) == 1

    def test_top_k_one(self, rag_service, sample_corpus):
        """Test top_k=1 returns single result."""
        request = QueryRequest(
            query="BERT",
            top_k=1,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        # Should return at most 1 result
        assert len(result.matches) <= 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Source Filtering
# ──────────────────────────────────────────────────────────────────────────────


class TestSourceFiltering:
    """Tests for source_id filtering."""

    def test_filter_by_source_id(self, rag_service, sample_corpus):
        """Test filtering by source_id."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
            source_ids=["paper_001"],
        )
        result = rag_service.retrieve(request)

        # All results should be from paper_001
        for match in result.matches:
            assert match.source_id == "paper_001"

    def test_filter_excludes_other_sources(self, rag_service, sample_corpus):
        """Test filter excludes other sources."""
        request = QueryRequest(
            query="BERT accuracy",
            top_k=5,
            corpus=sample_corpus,
            source_ids=["paper_001"],
        )
        result = rag_service.retrieve(request)

        # Should not include paper_002
        source_ids = {match.source_id for match in result.matches}
        assert "paper_002" not in source_ids

    def test_filter_multiple_sources(self, rag_service, sample_corpus):
        """Test filtering with multiple source_ids."""
        request = QueryRequest(
            query="BERT attention",
            top_k=5,
            corpus=sample_corpus,
            source_ids=["paper_001", "paper_002"],
        )
        result = rag_service.retrieve(request)

        # All results should be from allowed sources
        for match in result.matches:
            assert match.source_id in ["paper_001", "paper_002"]

    def test_filter_no_matching_sources(self, rag_service, sample_corpus):
        """Test filter with no matching sources."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
            source_ids=["paper_999"],
        )
        result = rag_service.retrieve(request)

        # Should return no matches
        assert len(result.matches) == 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Query Tokenization
# ──────────────────────────────────────────────────────────────────────────────


class TestQueryTokenization:
    """Tests for query tokenization and matching."""

    def test_simple_query_match(self, rag_service):
        """Test simple single-term query."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT is a model",
                start_char=0,
                end_char=15,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        assert len(result.matches) > 0

    def test_multi_term_query(self, rag_service):
        """Test query with multiple terms."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT language model",
                start_char=0,
                end_char=19,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request = QueryRequest(
            query="BERT language model",
            top_k=5,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        assert len(result.matches) > 0

    def test_case_insensitive_matching(self, rag_service):
        """Test matching is case-insensitive."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT achieves good results",
                start_char=0,
                end_char=26,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request_lower = QueryRequest(
            query="bert achieves",
            top_k=5,
            corpus=corpus,
        )
        request_upper = QueryRequest(
            query="BERT ACHIEVES",
            top_k=5,
            corpus=corpus,
        )

        result_lower = rag_service.retrieve(request_lower)
        result_upper = rag_service.retrieve(request_upper)

        # Both should match
        assert len(result_lower.matches) > 0
        assert len(result_upper.matches) > 0


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Match Content
# ──────────────────────────────────────────────────────────────────────────────


class TestMatchContent:
    """Tests for match content and metadata."""

    def test_match_has_required_fields(self, rag_service, sample_corpus):
        """Test RAGMatch has all required fields."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        for match in result.matches:
            assert isinstance(match, RAGMatch)
            assert match.chunk_id is not None
            assert match.source_id is not None
            assert match.score is not None
            assert match.text is not None
            assert match.start_char is not None
            assert match.end_char is not None

    def test_match_text_matches_corpus(self, rag_service, sample_corpus):
        """Test matched text corresponds to corpus chunk."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        for match in result.matches:
            # Find original chunk
            original = next(c for c in sample_corpus if c.chunk_id == match.chunk_id)
            assert match.text == original.text
            assert match.source_id == original.source_id

    def test_match_character_offsets_valid(self, rag_service, sample_corpus):
        """Test character offsets are valid."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        for match in result.matches:
            assert match.start_char >= 0
            assert match.end_char >= match.start_char
            assert match.end_char <= len(match.text) * 2  # Allow some flexibility


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Output Schema Validity
# ──────────────────────────────────────────────────────────────────────────────


class TestOutputSchema:
    """Tests for output schema validity."""

    def test_result_pydantic_model(self, rag_service, sample_corpus):
        """Test RAGResult is valid Pydantic model."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        assert isinstance(result, RAGResult)

        # Round-trip serialization
        result_dict = result.model_dump()
        restored = RAGResult(**result_dict)
        assert isinstance(restored, RAGResult)

    def test_match_pydantic_model(self, rag_service, sample_corpus):
        """Test RAGMatch is valid Pydantic model."""
        request = QueryRequest(
            query="BERT",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        for match in result.matches:
            # Round-trip serialization
            match_dict = match.model_dump()
            restored = RAGMatch(**match_dict)
            assert isinstance(restored, RAGMatch)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic retrieval."""

    def test_same_input_same_output(self, rag_service, sample_corpus):
        """Test same input produces same output."""
        request = QueryRequest(
            query="BERT accuracy",
            top_k=3,
            corpus=sample_corpus,
        )

        result1 = rag_service.retrieve(request)
        result2 = rag_service.retrieve(request)
        result3 = rag_service.retrieve(request)

        # All should have same number of matches
        assert len(result1.matches) == len(result2.matches) == len(result3.matches)

        # All matches should be identical
        for m1, m2, m3 in zip(result1.matches, result2.matches, result3.matches):
            assert m1.chunk_id == m2.chunk_id == m3.chunk_id
            assert m1.score == m2.score == m3.score

    def test_deterministic_ranking(self, rag_service):
        """Test ranking is deterministic."""
        corpus = [
            IngestionChunk(
                chunk_id=f"chunk_{i}",
                source_id="paper_001",
                page=1,
                text=f"BERT variant model {i} transformation",
                start_char=i,
                end_char=i + 30,
                text_hash=f"hash_{i}",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            )
            for i in range(5)
        ]

        request = QueryRequest(
            query="BERT transformation",
            top_k=5,
            corpus=corpus,
        )

        result1 = rag_service.retrieve(request)
        result2 = rag_service.retrieve(request)

        for r1, r2 in zip(result1.matches, result2.matches):
            assert r1.chunk_id == r2.chunk_id


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_long_query(self, rag_service, sample_corpus):
        """Test handling of very long query."""
        long_query = "BERT " * 100  # Repeat query term many times
        request = QueryRequest(
            query=long_query,
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        # Should handle without error
        assert isinstance(result, RAGResult)

    def test_special_characters_in_query(self, rag_service, sample_corpus):
        """Test query with special characters."""
        request = QueryRequest(
            query="BERT@#$%^&*()",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)

        # Should handle gracefully
        assert isinstance(result, RAGResult)

    def test_unicode_in_query(self, rag_service):
        """Test query with unicode characters."""
        corpus = [
            IngestionChunk(
                chunk_id="chunk_1",
                source_id="paper_001",
                page=1,
                text="BERT model 世界",
                start_char=0,
                end_char=15,
                text_hash="hash_1",
                context_id="ctx_1",
                numeric_strings=[],
                unit_strings=[],
                metric_names=[],
            ),
        ]

        request = QueryRequest(
            query="BERT 世界",
            top_k=5,
            corpus=corpus,
        )
        result = rag_service.retrieve(request)

        # Should handle unicode
        assert isinstance(result, RAGResult)

    def test_single_character_query(self, rag_service, sample_corpus):
        """Test single character query handling."""
        request = QueryRequest(
            query="a",
            top_k=5,
            corpus=sample_corpus,
        )
        result = rag_service.retrieve(request)
        
        # Should handle single char query
        assert isinstance(result, RAGResult)
