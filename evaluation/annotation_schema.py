"""Ground truth annotation schema for ScholarOS evaluation.

Defines schemas for annotated claims, clusters, and contradictions
used to evaluate pipeline quality.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnnotatedClaim(BaseModel):
    """A human-annotated ground truth claim."""

    claim_id: str = Field(..., description="Canonical claim identifier")
    paper_id: str = Field(..., description="Source paper")
    text: str = Field(..., description="Claim text")
    subject: str = Field(default="", description="Subject of the claim")
    predicate: str = Field(default="", description="Predicate (relationship)")
    object_value: str = Field(default="", description="Object value")
    claim_type: str = Field(default="empirical", description="Claim type: empirical/theoretical/methodological")
    is_valid: bool = Field(default=True, description="Whether this is a valid scientific claim")
    chunk_id: Optional[str] = Field(None, description="Source chunk identifier")


class AnnotatedCluster(BaseModel):
    """A human-annotated ground truth cluster."""

    cluster_id: str = Field(..., description="Cluster identifier")
    label: str = Field(..., description="Human-assigned cluster label")
    paper_ids: List[str] = Field(default_factory=list, description="Papers in this cluster")
    is_noise: bool = Field(default=False, description="Whether this is a noise cluster")


class AnnotatedContradiction(BaseModel):
    """A human-annotated ground truth contradiction."""

    contradiction_id: str = Field(..., description="Contradiction identifier")
    claim_a_id: str = Field(..., description="First claim in the contradiction")
    claim_b_id: str = Field(..., description="Second claim in the contradiction")
    relation_type: str = Field(default="contradicts", description="Relation: contradicts/qualifies/extends")
    description: Optional[str] = Field(None, description="Human description of the contradiction")


class PaperAnnotation(BaseModel):
    """Complete annotation for a single paper."""

    paper_id: str = Field(..., description="Paper identifier")
    title: str = Field(default="", description="Paper title")
    claims: List[AnnotatedClaim] = Field(default_factory=list)
    contradictions: List[AnnotatedContradiction] = Field(default_factory=list)
    cluster_label: Optional[str] = Field(None, description="Expected cluster label for this paper")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GroundTruth(BaseModel):
    """Complete ground truth dataset for evaluation."""

    version: str = Field(default="1.0.0", description="Dataset version")
    papers: List[PaperAnnotation] = Field(default_factory=list)
    clusters: List[AnnotatedCluster] = Field(default_factory=list)

    def get_all_claims(self) -> List[AnnotatedClaim]:
        """Return all annotated claims across all papers."""
        claims = []
        for paper in self.papers:
            claims.extend(paper.claims)
        return claims

    def get_claims_for_paper(self, paper_id: str) -> List[AnnotatedClaim]:
        for paper in self.papers:
            if paper.paper_id == paper_id:
                return paper.claims
        return []

    @classmethod
    def from_jsonl(cls, path: str) -> "GroundTruth":
        """Load from JSONL file (one PaperAnnotation per line)."""
        import json
        papers = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    papers.append(PaperAnnotation.model_validate(json.loads(line)))
        return cls(papers=papers)

    def to_jsonl(self, path: str) -> None:
        """Save to JSONL file."""
        import json
        with open(path, "w") as f:
            for paper in self.papers:
                f.write(paper.model_dump_json() + "\n")
