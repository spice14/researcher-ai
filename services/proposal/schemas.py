"""Schemas for the Proposal service.

Defines request/response contracts for converting validated hypotheses
and supporting evidence into structured research artifacts.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ProposalSection(str, Enum):
    """Canonical proposal sections."""
    NOVELTY = "novelty"
    MOTIVATION = "motivation"
    METHODOLOGY = "methodology"
    EXPECTED_OUTCOMES = "expected_outcomes"
    REFERENCES = "references"


class ProposalRequest(BaseModel):
    """Input schema for proposal generation."""

    hypothesis_id: str = Field(
        ..., description="ID of the validated hypothesis", min_length=1
    )
    statement: str = Field(
        ..., description="The hypothesis statement text", min_length=1
    )
    rationale: str = Field(
        default="", description="Rationale for the hypothesis"
    )
    assumptions: List[str] = Field(
        default_factory=list, description="Explicit assumptions"
    )
    supporting_claims: List[Dict] = Field(
        default_factory=list,
        description="Supporting claim dicts with claim_id, subject, predicate, object_raw, metric_canonical, context_id",
    )
    known_risks: List[str] = Field(
        default_factory=list, description="Known risks from hypothesis or critique"
    )
    critiques: List[Dict] = Field(
        default_factory=list,
        description="Critique dicts with counter_evidence, weak_assumptions, suggested_revisions",
    )
    paper_references: List[Dict] = Field(
        default_factory=list,
        description="Paper reference dicts with paper_id, title, authors, doi",
    )
    constraints: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional constraints (e.g., funding_agency, word_limit, format)",
    )


class SectionDraft(BaseModel):
    """A single generated section of the proposal."""

    section: ProposalSection = Field(..., description="Which section this is")
    heading: str = Field(..., description="Section heading text")
    content: str = Field(..., description="Section body text (Markdown)")
    citations_used: List[str] = Field(
        default_factory=list, description="paper_ids cited in this section"
    )


class ProposalResult(BaseModel):
    """Output schema for proposal generation."""

    proposal_id: str = Field(..., description="Generated proposal identifier")
    hypothesis_id: str = Field(..., description="Source hypothesis ID")
    sections: List[SectionDraft] = Field(..., description="Ordered proposal sections")
    full_markdown: str = Field(..., description="Assembled Markdown document")
    references: List[Dict] = Field(
        default_factory=list, description="Assembled reference list"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Non-fatal generation warnings"
    )
