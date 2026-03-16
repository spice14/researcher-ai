"""MCP (Model Context Protocol) Core — architectural foundation.

This module defines the MCP protocol that all tools must follow:
- Explicit tool manifests
- Deterministic execution contracts
- Structured tracing
- No hidden state

Tools implement MCPTool interface and register themselves globally.
Orchestrator invokes tools through the protocol, not directly.
"""

from core.mcp.mcp_manifest import MCPManifest, MCPCall
from core.mcp.mcp_tool import MCPTool
from core.mcp.registry import MCPRegistry, DuplicateToolError, ToolNotFoundError
from core.mcp.trace import TraceEntry, ExecutionTrace, hash_payload

__all__ = [
    "MCPManifest",
    "MCPCall",
    "MCPTool",
    "MCPRegistry",
    "DuplicateToolError",
    "ToolNotFoundError",
    "TraceEntry",
    "ExecutionTrace",
    "hash_payload",
]
