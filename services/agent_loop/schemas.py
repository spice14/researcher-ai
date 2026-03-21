"""Schemas for the agent loop MCP tool."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentLoopRequest(BaseModel):
    """Request to run hypothesis-critique loop."""

    claims: List[Dict[str, Any]] = Field(default_factory=list, description="Structured claims")
    contradictions: List[Dict[str, Any]] = Field(default_factory=list, description="Contradiction data")
    consensus_groups: List[Dict[str, Any]] = Field(default_factory=list, description="Consensus groups")
    constraints: str = Field(default="", description="User constraints")
    counter_evidence_chunks: List[Dict[str, Any]] = Field(default_factory=list, description="RAG chunks")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Max iterations")
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Stop threshold")


class AgentLoopResult(BaseModel):
    """Result from hypothesis-critique loop."""

    final_hypothesis: Optional[Dict[str, Any]] = Field(None, description="Final hypothesis")
    critiques: List[Dict[str, Any]] = Field(default_factory=list, description="All critiques produced")
    iterations_completed: int = Field(default=0, description="Number of iterations")
    stopped_reason: str = Field(default="", description="Why the loop stopped")
    converged: bool = Field(default=False, description="Whether the loop converged")
    confidence_rationale: Optional[str] = Field(None, description="Rationale for final confidence")
    trace_entries: List[Dict[str, Any]] = Field(default_factory=list, description="Execution trace")
    total_duration_ms: float = Field(default=0.0, description="Total duration")
