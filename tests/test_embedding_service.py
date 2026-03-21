"""Tests for the embedding service — dimension + determinism."""

import math
import pytest
from services.embedding.service import EmbeddingService
from services.embedding.schemas import EmbeddingRequest
from services.embedding.tool import EmbeddingTool


class TestEmbeddingService:
    """Unit tests for the embedding service with hash fallback."""

    def _make_service(self):
        """Create service that will use hash fallback (no models available)."""
        svc = EmbeddingService(model_name="nonexistent-model", ollama_base_url="http://nonexistent:9999")
        return svc

    def test_fallback_returns_correct_dimension(self):
        svc = self._make_service()
        assert svc.backend == "hash_fallback"
        assert svc.dimension == 384

        result = svc.embed(EmbeddingRequest(texts=["hello world"]))
        assert len(result.embeddings) == 1
        assert len(result.embeddings[0]) == 384
        assert result.dimension == 384

    def test_deterministic_embeddings(self):
        svc = self._make_service()
        r1 = svc.embed(EmbeddingRequest(texts=["test input"]))
        r2 = svc.embed(EmbeddingRequest(texts=["test input"]))
        assert r1.embeddings == r2.embeddings

    def test_different_texts_produce_different_embeddings(self):
        svc = self._make_service()
        r = svc.embed(EmbeddingRequest(texts=["alpha", "beta"]))
        assert len(r.embeddings) == 2
        assert r.embeddings[0] != r.embeddings[1]

    def test_unit_vector_normalization(self):
        svc = self._make_service()
        r = svc.embed(EmbeddingRequest(texts=["normalize me"]))
        emb = r.embeddings[0]
        norm = math.sqrt(sum(v * v for v in emb))
        assert abs(norm - 1.0) < 0.01

    def test_empty_texts_raises(self):
        svc = self._make_service()
        with pytest.raises(ValueError):
            svc.embed(EmbeddingRequest(texts=[]))

    def test_multiple_texts(self):
        svc = self._make_service()
        r = svc.embed(EmbeddingRequest(texts=["one", "two", "three"]))
        assert len(r.embeddings) == 3
        assert all(len(e) == 384 for e in r.embeddings)


class TestEmbeddingTool:
    """MCP contract tests for the embedding tool."""

    def test_manifest(self):
        svc = EmbeddingService(model_name="x", ollama_base_url="http://x:9999")
        tool = EmbeddingTool(service=svc)
        m = tool.manifest()
        assert m.name == "embedding"
        assert "texts" in m.input_schema["properties"]

    def test_call(self):
        svc = EmbeddingService(model_name="x", ollama_base_url="http://x:9999")
        tool = EmbeddingTool(service=svc)
        result = tool.call({"texts": ["hello", "world"]})
        assert len(result["embeddings"]) == 2
        assert result["dimension"] == 384

    def test_missing_texts_raises(self):
        svc = EmbeddingService(model_name="x", ollama_base_url="http://x:9999")
        tool = EmbeddingTool(service=svc)
        with pytest.raises(ValueError, match="texts is required"):
            tool.call({})
