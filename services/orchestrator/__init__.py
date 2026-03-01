"""Deterministic DAG orchestrator.

PRIMARY: MCPOrchestrator (uses MCP tool layer for pure separation)
LEGACY: Orchestrator (deprecated - use MCP layer instead)
"""

from services.orchestrator.schemas import (
    ExecutionLog,
    Task,
    TaskResult,
    Workflow,
    WorkflowRequest,
)
from services.orchestrator.service import Orchestrator as LegacyOrchestrator
from services.orchestrator.mcp_orchestrator import MCPOrchestrator

# MCP orchestrator is the primary interface
Orchestrator = MCPOrchestrator

__all__ = [
    "Orchestrator",
    "MCPOrchestrator",
    "LegacyOrchestrator",
    "Task",
    "TaskResult",
    "Workflow",
    "WorkflowRequest",
    "ExecutionLog",
]
