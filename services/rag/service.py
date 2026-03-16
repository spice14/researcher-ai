"""Deterministic RAG service (scaffold).

Purpose:
- Provide deterministic retrieval over a provided corpus.
- Establish a testable interface ahead of vector DB integration.

Inputs/Outputs:
- Input: QueryRequest
- Output: RAGResult

Schema References:
- services.rag.schemas
- services.ingestion.schemas.IngestionChunk

Failure Modes:
- Empty query fails schema validation
- Empty corpus returns zero matches with warning

Testing Strategy:
- Unit tests validate stable ranking and filtering.
"""

from __future__ import annotations

import re
from typing import Iterable, List

from services.rag.schemas import QueryRequest, RAGMatch, RAGResult

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
    """Deterministic retrieval implementation (lexical overlap)."""

    def retrieve(self, request: QueryRequest) -> RAGResult:
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
