"""RAG service with semantic retrieval via Chroma and lexical fallback.

Purpose:
- Provide semantic retrieval over indexed content via vector store
- Fall back to lexical overlap when vector store is unavailable
- Support both corpus-based (in-memory) and index-based (persistent) retrieval

Inputs/Outputs:
- Input: QueryRequest
- Output: RAGResult

Failure Modes:
- Empty query fails schema validation
- Empty corpus returns zero matches with warning
- Vector store unavailable -> lexical fallback
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from services.rag.schemas import QueryRequest, RAGMatch, RAGResult

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def _score(query_tokens: List[str], text_tokens: List[str]) -> float:
    if not query_tokens:
        return 0.0
    text_set = set(text_tokens)
    hits = sum(1 for t in query_tokens if t in text_set)
    return hits / float(len(query_tokens))


class RAGService:
    """Retrieval service with semantic (Chroma) and lexical fallback."""

    def __init__(
        self,
        vector_store=None,
        embedding_service=None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    def retrieve(self, request: QueryRequest) -> RAGResult:
        """Retrieve matching chunks. Uses semantic search if available, else lexical."""
        # Try semantic retrieval first
        if self._vector_store is not None and self._embedding_service is not None:
            try:
                return self._semantic_retrieve(request)
            except Exception as exc:
                logger.warning("Semantic retrieval failed, falling back to lexical: %s", exc)

        # Lexical fallback
        return self._lexical_retrieve(request)

    def _semantic_retrieve(self, request: QueryRequest) -> RAGResult:
        """Semantic retrieval via embedding + vector store."""
        from services.embedding.schemas import EmbeddingRequest
        from services.vectorstore.schemas import VectorQueryRequest

        emb_result = self._embedding_service.embed(
            EmbeddingRequest(texts=[request.query])
        )
        query_embedding = emb_result.embeddings[0]

        where_filter = None
        if request.source_ids:
            # Chroma supports $in for list filters
            where_filter = {"source_id": {"$in": request.source_ids}} if len(request.source_ids) > 1 else {"source_id": request.source_ids[0]}

        vq = VectorQueryRequest(
            query_embedding=query_embedding,
            top_k=request.top_k,
            where=where_filter,
        )
        vresult = self._vector_store.query(vq)

        matches = []
        for m in vresult.matches:
            matches.append(
                RAGMatch(
                    chunk_id=m.id,
                    source_id=m.metadata.get("source_id", ""),
                    score=m.score,
                    text=m.document or "",
                    start_char=int(m.metadata.get("start_char", 0)),
                    end_char=int(m.metadata.get("end_char", 0)),
                )
            )

        return RAGResult(
            query=request.query,
            retrieval_method="semantic_chroma_v1",
            matches=matches,
            warnings=[],
        )

    def _lexical_retrieve(self, request: QueryRequest) -> RAGResult:
        """Original lexical overlap retrieval."""
        warnings: List[str] = []
        if not request.corpus:
            warnings.append("empty corpus provided; no matches returned")
            return RAGResult(
                query=request.query,
                retrieval_method="lexical_overlap_v1",
                matches=[],
                warnings=warnings,
            )

        query_tokens = _tokenize(request.query)
        if not query_tokens:
            warnings.append("query contains no searchable tokens")

        matches: List[RAGMatch] = []
        for chunk in request.corpus:
            if request.source_ids and chunk.source_id not in request.source_ids:
                continue
            score = _score(query_tokens, _tokenize(chunk.text))
            if score <= 0.0:
                continue
            matches.append(
                RAGMatch(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    score=score,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                )
            )

        matches.sort(key=lambda m: (-m.score, m.chunk_id))

        return RAGResult(
            query=request.query,
            retrieval_method="lexical_overlap_v1",
            matches=matches[: request.top_k],
            warnings=warnings,
        )
