"""Schemas for the literature mapping service."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MappingRequest(BaseModel):
    """Request to build a literature map."""

    seed_paper_id: Optional[str] = Field(None, description="Seed paper ID for contextual mapping")
    topic: Optional[str] = Field(None, description="Topic description or abstract")
    collection: str = Field(default="scholaros_chunks", description="Vector store collection")
    top_k: int = Field(default=50, ge=5, le=200, description="Number of papers to retrieve")
    min_cluster_size: int = Field(default=3, ge=2, description="Minimum cluster size for HDBSCAN")


class MappingResult(BaseModel):
    """Result of literature mapping."""

    map_id: str = Field(..., description="Cluster map identifier")
    seed_paper_id: Optional[str] = Field(None, description="Seed paper if used")
    clusters: List[Dict] = Field(default_factory=list, description="Cluster definitions")
    noise_paper_ids: List[str] = Field(default_factory=list, description="Papers not assigned to any cluster")
    paper_count: int = Field(default=0, description="Total papers processed")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
