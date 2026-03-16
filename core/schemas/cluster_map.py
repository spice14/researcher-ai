"""Structured literature map schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ClusterProvenance(BaseModel):
    """Evidence backing a cluster label or grouping."""

    paper_id: str = Field(..., description="Paper identifier", min_length=1)
    chunk_id: Optional[str] = Field(None, description="Optional chunk identifier")
    snippet: str = Field(..., description="Supporting text snippet", min_length=1)

    @field_validator("paper_id", "snippet")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v


class LiteratureCluster(BaseModel):
    """One cluster inside a literature map."""

    cluster_id: str = Field(..., description="Cluster identifier", min_length=1)
    label: str = Field(..., description="Human-readable cluster label", min_length=1)
    representative_paper_ids: List[str] = Field(
        default_factory=list,
        description="Representative papers nearest the centroid",
    )
    boundary_paper_ids: List[str] = Field(
        default_factory=list,
        description="Boundary papers near the cluster edge",
    )
    centroid_embedding: List[float] = Field(
        default_factory=list,
        description="Deterministic centroid embedding vector",
    )

    @field_validator("cluster_id", "label")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @field_validator("representative_paper_ids", "boundary_paper_ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("Paper identifiers must be non-empty")
        return v


class ClusterMap(BaseModel):
    """Semantic map of literature around a seed paper or topic."""

    map_id: str = Field(..., description="Cluster map identifier", min_length=1)
    seed_paper_id: Optional[str] = Field(None, description="Seed paper identifier if one was used")
    clusters: List[LiteratureCluster] = Field(default_factory=list, description="Discovered literature clusters")
    provenance: List[ClusterProvenance] = Field(
        default_factory=list,
        description="Evidence snippets explaining cluster labels and grouping",
    )

    @field_validator("map_id")
    @classmethod
    def validate_map_id(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("map_id must be non-empty")
        return v