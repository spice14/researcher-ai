"""Schemas for the consolidation service."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConsolidationRequest(BaseModel):
    """Request to consolidate analysis results."""

    hypothesis: Optional[Dict[str, Any]] = Field(None, description="Final hypothesis from loop")
    beliefs: List[Dict[str, Any]] = Field(default_factory=list, description="Belief states")
    clusters: List[Dict[str, Any]] = Field(default_factory=list, description="Literature clusters")
    contradictions: List[Dict[str, Any]] = Field(default_factory=list, description="Contradiction data")
    claims: List[Dict[str, Any]] = Field(default_factory=list, description="All claims")
    session_id: Optional[str] = Field(None, description="Session identifier")


class ConsolidationResult(BaseModel):
    """Consolidated analysis summary."""

    summary: str = Field(..., description="Human-readable analysis summary")
    key_findings: List[str] = Field(default_factory=list, description="Key findings")
    evidence_gaps: List[str] = Field(default_factory=list, description="Identified evidence gaps")
    confidence_assessment: str = Field(default="", description="Overall confidence assessment")
    hypothesis_status: str = Field(default="", description="Final hypothesis status")
    cluster_count: int = Field(default=0, description="Number of literature clusters")
    claim_count: int = Field(default=0, description="Total claims analyzed")
    contradiction_count: int = Field(default=0, description="Total contradictions found")
