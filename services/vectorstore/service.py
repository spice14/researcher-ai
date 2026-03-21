"""Vector store service wrapping Chroma for persistent semantic storage.

Purpose:
- Provide add/query/delete operations against a Chroma vector database
- Support graceful fallback to in-memory store when Chroma is unavailable
- All operations are stateless from the caller's perspective

Inputs/Outputs:
- add_embeddings: VectorAddRequest -> dict with count
- query: VectorQueryRequest -> VectorQueryResult
- delete: VectorDeleteRequest -> dict with count

Failure Modes:
- Chroma unreachable -> fall back to in-memory store with warning
- Empty embeddings -> ValueError
- Mismatched lengths -> ValueError

Testing Strategy:
- Unit tests with in-memory fallback
- Integration tests against Chroma container
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from services.vectorstore.schemas import (
    VectorAddRequest,
    VectorDeleteRequest,
    VectorMatch,
    VectorQueryRequest,
    VectorQueryResult,
)

logger = logging.getLogger(__name__)


class InMemoryVectorStore:
    """Fallback in-memory vector store for testing and offline use."""

    def __init__(self) -> None:
        self._collections: Dict[str, Dict[str, Any]] = {}

    def _get_collection(self, name: str) -> Dict[str, Any]:
        if name not in self._collections:
            self._collections[name] = {
                "ids": [],
                "embeddings": [],
                "documents": [],
                "metadatas": [],
            }
        return self._collections[name]

    def add(
        self,
        collection: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, str]],
    ) -> int:
        coll = self._get_collection(collection)
        for i, id_ in enumerate(ids):
            if id_ in coll["ids"]:
                idx = coll["ids"].index(id_)
                coll["embeddings"][idx] = embeddings[i]
                coll["documents"][idx] = documents[i] if i < len(documents) else ""
                coll["metadatas"][idx] = metadatas[i] if i < len(metadatas) else {}
            else:
                coll["ids"].append(id_)
                coll["embeddings"].append(embeddings[i])
                coll["documents"].append(documents[i] if i < len(documents) else "")
                coll["metadatas"].append(metadatas[i] if i < len(metadatas) else {})
        return len(ids)

    def query(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict] = None,
    ) -> VectorQueryResult:
        coll = self._get_collection(collection)
        if not coll["ids"]:
            return VectorQueryResult(matches=[], collection=collection, query_count=0)

        scores = []
        for i, emb in enumerate(coll["embeddings"]):
            score = _cosine_similarity(query_embedding, emb)
            scores.append((i, score))

        scores.sort(key=lambda x: -x[1])
        matches = []
        for idx, score in scores[:top_k]:
            meta = coll["metadatas"][idx] if idx < len(coll["metadatas"]) else {}
            if where and not _matches_filter(meta, where):
                continue
            matches.append(
                VectorMatch(
                    id=coll["ids"][idx],
                    score=round(score, 6),
                    document=coll["documents"][idx] if idx < len(coll["documents"]) else None,
                    metadata=meta,
                )
            )

        return VectorQueryResult(
            matches=matches[:top_k],
            collection=collection,
            query_count=len(matches[:top_k]),
        )

    def delete(self, collection: str, ids: List[str]) -> int:
        coll = self._get_collection(collection)
        removed = 0
        for id_ in ids:
            if id_ in coll["ids"]:
                idx = coll["ids"].index(id_)
                coll["ids"].pop(idx)
                coll["embeddings"].pop(idx)
                if idx < len(coll["documents"]):
                    coll["documents"].pop(idx)
                if idx < len(coll["metadatas"]):
                    coll["metadatas"].pop(idx)
                removed += 1
        return removed


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _matches_filter(metadata: Dict[str, str], where: Dict) -> bool:
    for key, value in where.items():
        if metadata.get(key) != value:
            return False
    return True


class VectorStoreService:
    """Vector store service with Chroma backend and in-memory fallback."""

    def __init__(
        self,
        chroma_host: Optional[str] = None,
        chroma_port: Optional[int] = None,
    ) -> None:
        self._chroma_host = chroma_host or os.environ.get("CHROMA_HOST", "localhost")
        self._chroma_port = chroma_port or int(os.environ.get("CHROMA_PORT", "8001"))
        self._client = None
        self._fallback = InMemoryVectorStore()
        self._using_fallback = False
        self._init_client()

    def _init_client(self) -> None:
        try:
            import chromadb

            self._client = chromadb.HttpClient(
                host=self._chroma_host,
                port=self._chroma_port,
            )
            # Test connection
            self._client.heartbeat()
            logger.info("Connected to Chroma at %s:%s", self._chroma_host, self._chroma_port)
        except Exception as exc:
            logger.warning(
                "Chroma unavailable at %s:%s, using in-memory fallback: %s",
                self._chroma_host,
                self._chroma_port,
                exc,
            )
            self._client = None
            self._using_fallback = True

    def add_embeddings(self, request: VectorAddRequest) -> Dict[str, Any]:
        if len(request.ids) != len(request.embeddings):
            raise ValueError(
                f"ids length ({len(request.ids)}) must match embeddings length ({len(request.embeddings)})"
            )

        documents = request.documents or [""] * len(request.ids)
        metadatas = request.metadatas or [{}] * len(request.ids)

        if self._client and not self._using_fallback:
            try:
                collection = self._client.get_or_create_collection(
                    name=request.collection,
                    metadata={"hnsw:space": "cosine"},
                )
                collection.upsert(
                    ids=request.ids,
                    embeddings=request.embeddings,
                    documents=documents if any(d for d in documents) else None,
                    metadatas=metadatas if any(m for m in metadatas) else None,
                )
                return {"count": len(request.ids), "collection": request.collection, "backend": "chroma"}
            except Exception as exc:
                logger.warning("Chroma add failed, falling back to in-memory: %s", exc)
                self._using_fallback = True

        count = self._fallback.add(
            request.collection, request.ids, request.embeddings, documents, metadatas
        )
        return {"count": count, "collection": request.collection, "backend": "in_memory"}

    def query(self, request: VectorQueryRequest) -> VectorQueryResult:
        if self._client and not self._using_fallback:
            try:
                collection = self._client.get_or_create_collection(
                    name=request.collection,
                    metadata={"hnsw:space": "cosine"},
                )
                results = collection.query(
                    query_embeddings=[request.query_embedding],
                    n_results=request.top_k,
                    where=request.where,
                    include=["documents", "metadatas", "distances"],
                )

                matches = []
                if results["ids"] and results["ids"][0]:
                    for i, id_ in enumerate(results["ids"][0]):
                        distance = results["distances"][0][i] if results.get("distances") else 0.0
                        score = max(0.0, 1.0 - distance)
                        doc = results["documents"][0][i] if results.get("documents") and results["documents"][0] else None
                        meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                        matches.append(
                            VectorMatch(
                                id=id_,
                                score=round(score, 6),
                                document=doc,
                                metadata=meta or {},
                            )
                        )

                return VectorQueryResult(
                    matches=matches,
                    collection=request.collection,
                    query_count=len(matches),
                )
            except Exception as exc:
                logger.warning("Chroma query failed, falling back to in-memory: %s", exc)
                self._using_fallback = True

        return self._fallback.query(
            request.collection, request.query_embedding, request.top_k, request.where
        )

    def delete(self, request: VectorDeleteRequest) -> Dict[str, Any]:
        if self._client and not self._using_fallback:
            try:
                collection = self._client.get_or_create_collection(name=request.collection)
                collection.delete(ids=request.ids)
                return {"count": len(request.ids), "collection": request.collection, "backend": "chroma"}
            except Exception as exc:
                logger.warning("Chroma delete failed, falling back to in-memory: %s", exc)
                self._using_fallback = True

        count = self._fallback.delete(request.collection, request.ids)
        return {"count": count, "collection": request.collection, "backend": "in_memory"}

    @property
    def is_using_fallback(self) -> bool:
        return self._using_fallback
