"""Schemas for the metadata store service."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PaperRecord(BaseModel):
    """Paper metadata for storage."""

    paper_id: str = Field(..., description="Unique paper identifier", min_length=1)
    title: str = Field(..., description="Paper title", min_length=1)
    authors: List[str] = Field(default_factory=list, description="Author names")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    doi: Optional[str] = Field(None, description="DOI")
    arxiv_id: Optional[str] = Field(None, description="arXiv ID")
    pdf_path: str = Field(default="", description="Path to source PDF")
    ingestion_timestamp: Optional[datetime] = Field(None, description="When ingested")
    chunk_count: int = Field(default=0, description="Number of chunks produced")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Extra metadata")


class ClaimRecord(BaseModel):
    """Claim metadata for storage."""

    claim_id: str = Field(..., description="Unique claim identifier", min_length=1)
    paper_id: str = Field(..., description="Source paper ID", min_length=1)
    text: str = Field(default="", description="Claim text")
    subject: str = Field(default="", description="Claim subject")
    predicate: str = Field(default="", description="Claim predicate")
    object_value: str = Field(default="", description="Claim object")
    claim_type: str = Field(default="performance", description="Claim type")
    context_id: Optional[str] = Field(None, description="Experimental context ID")
    confidence_level: str = Field(default="low", description="Confidence level")


class SessionRecord(BaseModel):
    """Session metadata for storage."""

    session_id: str = Field(..., description="Session identifier", min_length=1)
    user_input: str = Field(default="", description="User input")
    phase: str = Field(default="init", description="Current phase")
    created_at: Optional[datetime] = Field(None, description="Creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    paper_ids: List[str] = Field(default_factory=list, description="Associated papers")
    hypothesis_ids: List[str] = Field(default_factory=list, description="Associated hypotheses")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra session data")


class HypothesisRecord(BaseModel):
    """Hypothesis metadata for storage."""

    hypothesis_id: str = Field(..., description="Hypothesis identifier", min_length=1)
    session_id: str = Field(..., description="Session ID", min_length=1)
    statement: str = Field(default="", description="Hypothesis statement")
    confidence_score: Optional[float] = Field(None, description="Confidence score")
    iteration_number: int = Field(default=1, description="Iteration number")
    created_at: Optional[datetime] = Field(None, description="Creation time")


class ProposalRecord(BaseModel):
    """Proposal metadata for storage."""

    proposal_id: str = Field(..., description="Proposal identifier", min_length=1)
    hypothesis_id: str = Field(..., description="Source hypothesis ID", min_length=1)
    session_id: str = Field(..., description="Session ID", min_length=1)
    markdown: str = Field(default="", description="Full markdown content")
    created_at: Optional[datetime] = Field(None, description="Creation time")
