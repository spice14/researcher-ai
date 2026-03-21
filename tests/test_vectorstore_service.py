"""Tests for the vector store service — Chroma CRUD + MCP contract."""

import pytest
from services.vectorstore.service import VectorStoreService, InMemoryVectorStore
from services.vectorstore.schemas import (
    VectorAddRequest,
    VectorDeleteRequest,
    VectorQueryRequest,
    VectorQueryResult,
)
from services.vectorstore.tool import VectorStoreTool


class TestInMemoryVectorStore:
    """Unit tests for the in-memory fallback vector store."""

    def test_add_and_query_round_trip(self):
        store = InMemoryVectorStore()
        store.add(
            "test_col",
            ids=["id1", "id2"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            documents=["doc one", "doc two"],
            metadatas=[{"source": "a"}, {"source": "b"}],
        )

        result = store.query("test_col", query_embedding=[1.0, 0.0, 0.0], top_k=2)
        assert isinstance(result, VectorQueryResult)
        assert len(result.matches) == 2
        assert result.matches[0].id == "id1"
        assert result.matches[0].score > 0.99

    def test_delete(self):
        store = InMemoryVectorStore()
        store.add("col", ids=["a", "b"], embeddings=[[1, 0], [0, 1]], documents=["", ""], metadatas=[{}, {}])
        removed = store.delete("col", ["a"])
        assert removed == 1

        result = store.query("col", query_embedding=[1, 0], top_k=10)
        assert len(result.matches) == 1
        assert result.matches[0].id == "b"

    def test_upsert_behavior(self):
        store = InMemoryVectorStore()
        store.add("col", ids=["a"], embeddings=[[1, 0]], documents=["old"], metadatas=[{}])
        store.add("col", ids=["a"], embeddings=[[0, 1]], documents=["new"], metadatas=[{}])

        result = store.query("col", query_embedding=[0, 1], top_k=1)
        assert len(result.matches) == 1
        assert result.matches[0].id == "a"
        assert result.matches[0].score > 0.99

    def test_empty_query(self):
        store = InMemoryVectorStore()
        result = store.query("empty_col", query_embedding=[1, 0], top_k=5)
        assert len(result.matches) == 0

    def test_metadata_filter(self):
        store = InMemoryVectorStore()
        store.add(
            "col",
            ids=["a", "b"],
            embeddings=[[1, 0], [0, 1]],
            documents=["", ""],
            metadatas=[{"type": "table"}, {"type": "text"}],
        )
        result = store.query("col", query_embedding=[1, 0], top_k=10, where={"type": "text"})
        assert all(m.metadata.get("type") == "text" for m in result.matches)


class TestVectorStoreService:
    """Tests for VectorStoreService with in-memory fallback."""

    def test_add_and_query(self):
        svc = VectorStoreService(chroma_host="nonexistent", chroma_port=9999)
        assert svc.is_using_fallback

        add_result = svc.add_embeddings(VectorAddRequest(
            collection="test",
            ids=["v1", "v2", "v3"],
            embeddings=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            documents=["alpha", "beta", "gamma"],
        ))
        assert add_result["count"] == 3
        assert add_result["backend"] == "in_memory"

        query_result = svc.query(VectorQueryRequest(
            collection="test",
            query_embedding=[1, 0, 0],
            top_k=2,
        ))
        assert isinstance(query_result, VectorQueryResult)
        assert query_result.query_count <= 2
        assert query_result.matches[0].id == "v1"

    def test_delete(self):
        svc = VectorStoreService(chroma_host="nonexistent", chroma_port=9999)
        svc.add_embeddings(VectorAddRequest(
            collection="del_test",
            ids=["x1", "x2"],
            embeddings=[[1, 0], [0, 1]],
        ))
        del_result = svc.delete(VectorDeleteRequest(collection="del_test", ids=["x1"]))
        assert del_result["count"] == 1

    def test_mismatched_lengths_raises(self):
        svc = VectorStoreService(chroma_host="nonexistent", chroma_port=9999)
        with pytest.raises(ValueError, match="ids length"):
            svc.add_embeddings(VectorAddRequest(
                collection="test",
                ids=["a"],
                embeddings=[[1, 0], [0, 1]],
            ))


class TestVectorStoreTool:
    """MCP contract tests for the vector store tool."""

    def test_manifest(self):
        tool = VectorStoreTool(service=VectorStoreService(chroma_host="x", chroma_port=9999))
        m = tool.manifest()
        assert m.name == "vector_store"
        assert m.version == "1.0.0"
        assert "operation" in m.input_schema["properties"]

    def test_add_call(self):
        svc = VectorStoreService(chroma_host="x", chroma_port=9999)
        tool = VectorStoreTool(service=svc)
        result = tool.call({
            "operation": "add",
            "ids": ["t1"],
            "embeddings": [[0.5, 0.5]],
        })
        assert result["count"] == 1

    def test_query_call(self):
        svc = VectorStoreService(chroma_host="x", chroma_port=9999)
        tool = VectorStoreTool(service=svc)
        tool.call({
            "operation": "add",
            "ids": ["t1"],
            "embeddings": [[1.0, 0.0]],
            "documents": ["hello"],
        })
        result = tool.call({
            "operation": "query",
            "query_embedding": [1.0, 0.0],
            "top_k": 1,
        })
        assert len(result["matches"]) == 1

    def test_delete_call(self):
        svc = VectorStoreService(chroma_host="x", chroma_port=9999)
        tool = VectorStoreTool(service=svc)
        tool.call({"operation": "add", "ids": ["d1"], "embeddings": [[1, 0]]})
        result = tool.call({"operation": "delete", "ids": ["d1"]})
        assert result["count"] == 1

    def test_unknown_operation_raises(self):
        tool = VectorStoreTool(service=VectorStoreService(chroma_host="x", chroma_port=9999))
        with pytest.raises(ValueError, match="Unknown operation"):
            tool.call({"operation": "invalid"})
