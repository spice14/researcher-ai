"""MCP Tool Manifest Schema — defines tool interface contract.

A strict Pydantic schema that every MCP tool must implement.
Tools are discoverable, self-describing, and language-agnostic.

No runtime behavior here — just schema definition.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class MCPManifest(BaseModel):
    """Tool manifest defining input/output contracts.
    
    This is the canonical definition of what a tool does.
    All MCP tools MUST provide a manifest conforming to this schema.
    """

    name: str = Field(
        ...,
        description="Unique tool identifier (e.g., 'ingestion', 'extraction', 'normalization')",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z_]+$"
    )
    
    version: str = Field(
        ...,
        description="Tool version (semantic versioning with optional suffix)",
        pattern=r"^\d+\.\d+\.\d+(-[\w\.]+)?$"
    )
    
    description: str = Field(
        ...,
        description="Human-readable tool description",
        min_length=10,
        max_length=500
    )
    
    input_schema: Dict[str, Any] = Field(
        ...,
        description="JSON Schema for input payload. Must support validation."
    )
    
    output_schema: Dict[str, Any] = Field(
        ...,
        description="JSON Schema for output payload. Must support validation."
    )
    
    deterministic: bool = Field(
        default=True,
        description="Whether tool produces identical outputs for identical inputs"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "normalization",
                "version": "1.0.0",
                "description": "Canonicalizes metric names and binds numeric values",
                "input_schema": {"type": "object", "properties": {"claim": {"type": "object"}}},
                "output_schema": {"type": "object", "properties": {"normalized": {"type": "object"}}},
                "deterministic": True
            }
        }
    }


class MCPCall(BaseModel):
    """Record of a single MCP tool invocation."""
    
    tool: str = Field(..., description="Tool name from manifest")
    payload: Dict[str, Any] = Field(..., description="Input payload")
    result: Dict[str, Any] = Field(..., description="Output result")
    status: str = Field(..., description="'success' or 'error'")
    error_message: Optional[str] = Field(None, description="Error message if status='error'")
