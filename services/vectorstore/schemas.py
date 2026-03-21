"""Schemas for the vector store service."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class VectorAddRequest(BaseModel):
    """Request to add embeddings to the vector store."""

    collection: str = Field(
        default="scholaros_chunks",
        description="Collection name",
        min_length=1,
    )
    ids: List[str] = Field(..., description="Unique identifiers for each embedding", min_length=1)
    embeddings: List[List[float]] = Field(..., description="Embedding vectors", min_length=1)
    documents: List[str] = Field(default_factory=list, description="Optional raw text documents")
    metadatas: List[Dict[str, str]] = Field(default_factory=list, description="Per-embedding metadata")

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        for item in v:
            if not item.strip():
                raise ValueError("IDs must be non-empty strings")
        return v


class VectorQueryRequest(BaseModel):
    """Request to query the vector store."""

    collection: str = Field(
        default="scholaros_chunks",
        description="Collection name",
        min_length=1,
    )
    query_embedding: List[float] = Field(..., description="Query embedding vector", min_length=1)
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    where: Optional[Dict] = Field(default=None, description="Optional metadata filter")


class VectorDeleteRequest(BaseModel):
    """Request to delete embeddings from the vector store."""

    collection: str = Field(
        default="scholaros_chunks",
        description="Collection name",
        min_length=1,
    )
    ids: List[str] = Field(..., description="IDs to delete", min_length=1)


class VectorMatch(BaseModel):
    """Single vector query result."""

    id: str = Field(..., description="Document ID")
    score: float = Field(..., description="Cosine similarity score")
    document: Optional[str] = Field(None, description="Original document text")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Document metadata")


class VectorQueryResult(BaseModel):
    """Result of a vector query."""

    matches: List[VectorMatch] = Field(default_factory=list, description="Ranked results")
    collection: str = Field(..., description="Collection queried")
    query_count: int = Field(default=0, description="Number of results returned")
