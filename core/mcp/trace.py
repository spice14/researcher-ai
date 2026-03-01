"""MCP Trace Logging — deterministic execution audit trail.

Orchestrator logs every tool invocation with input/output hashes.
This enables:
- Reproducibility verification
- Execution auditing
- Determinism validation
- Cache key generation
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import json


class TraceEntry(BaseModel):
    """Single tool invocation in execution trace.
    
    Records what was called, with proof of inputs and outputs.
    Uses content hashing for determinism verification.
    """
    
    sequence: int = Field(..., description="Position in execution order (0-indexed)")
    tool: str = Field(..., description="Tool name")
    input_hash: str = Field(..., description="SHA256 of sorted input JSON")
    output_hash: str = Field(..., description="SHA256 of sorted output JSON")
    timestamp: datetime = Field(..., description="When invocation occurred")
    status: str = Field(..., description="'success' or 'error'")
    error_message: Optional[str] = Field(None, description="Error if present")
    duration_ms: float = Field(..., description="Execution time in milliseconds", ge=0)


class ExecutionTrace(BaseModel):
    """Complete trace of a pipeline execution.
    
    Used to verify determinism: two runs with same inputs
    should produce identical traces and final_output_hash.
    """
    
    session_id: str = Field(..., description="Unique session identifier")
    started_at: datetime = Field(..., description="Pipeline start time")
    completed_at: datetime = Field(..., description="Pipeline end time")
    entries: List[TraceEntry] = Field(default_factory=list, description="Ordered tool invocations")
    final_output_hash: str = Field(..., description="SHA256 of final pipeline output")
    final_output: Dict[str, Any] = Field(..., description="Final pipeline output payload")
    pipeline_definition: List[str] = Field(..., description="Ordered tool names executed")
    
    @property
    def duration_ms(self) -> float:
        """Total pipeline execution time in milliseconds."""
        delta = self.completed_at - self.started_at
        return delta.total_seconds() * 1000
    
    @property
    def success(self) -> bool:
        """Whether all steps completed successfully."""
        return all(e.status == "success" for e in self.entries)


def hash_payload(payload: dict) -> str:
    """
    Deterministic hash of a payload dict.
    
    Args:
        payload: Dict to hash
    
    Returns:
        SHA256 hex string of sorted JSON representation
    """
    # Sort JSON to ensure deterministic ordering
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode()).hexdigest()
