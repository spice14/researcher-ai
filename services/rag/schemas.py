"""Schemas for deterministic RAG service."""

from typing import List, Optional
from pydantic import BaseModel, Field

from services.ingestion.schemas import IngestionChunk


class QueryRequest(BaseModel):
    """Input schema for retrieval."""

    query: str = Field(..., description="User query", min_length=1)
    top_k: int = Field(5, ge=1, le=50, description="Number of matches to return")
    corpus: List[IngestionChunk] = Field(..., description="Corpus to search (scaffold)")
    source_ids: Optional[List[str]] = Field(None, description="Optional source filter")


class RAGMatch(BaseModel):
    """Single retrieval match."""

    chunk_id: str = Field(..., description="Chunk identifier")
    source_id: str = Field(..., description="Origin source identifier")
    score: float = Field(..., ge=0.0, description="Retrieval score")
    text: str = Field(..., description="Matched text")
    start_char: int = Field(..., ge=0, description="Start offset")
    end_char: int = Field(..., ge=0, description="End offset")


class RAGResult(BaseModel):
    """Output schema for retrieval."""

    query: str = Field(..., description="Echoed query")
    retrieval_method: str = Field(..., description="Retrieval method identifier")
    matches: List[RAGMatch] = Field(..., description="Ranked matches")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal retrieval warnings")
