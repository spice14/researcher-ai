"""Schemas for the embedding service."""

from typing import List, Optional

from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request to generate embeddings."""

    texts: List[str] = Field(..., description="Texts to embed", min_length=1)
    model: Optional[str] = Field(None, description="Model override")


class EmbeddingResult(BaseModel):
    """Result of embedding generation."""

    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    model: str = Field(..., description="Model used")
    dimension: int = Field(..., description="Embedding dimension")
