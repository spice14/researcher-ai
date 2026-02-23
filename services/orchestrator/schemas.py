"""Orchestrator schemas for deterministic DAG execution."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    """A single task in a DAG workflow."""

    task_id: str = Field(description="Unique task identifier")
    component: str = Field(
        description="Component name (e.g., 'ingestion', 'extraction', 'normalization')"
    )
    input_schema: str = Field(description="Input schema name")
    output_schema: str = Field(description="Output schema name")
    dependencies: List[str] = Field(
        default_factory=list, description="Task IDs that must complete before this task"
    )


class Workflow(BaseModel):
    """A deterministic workflow as a directed acyclic graph."""

    workflow_id: str = Field(description="Unique workflow identifier")
    description: str = Field(description="Human-readable workflow description")
    tasks: List[Task] = Field(description="Tasks in topological order")


class WorkflowRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_id: str = Field(description="ID of workflow to execute")
    input_data: Dict[str, Any] = Field(
        description="Initial input data for the workflow"
    )


class ExecutionLog(BaseModel):
    """Log entry for a single task execution."""

    task_id: str = Field(description="Task identifier")
    component: str = Field(description="Component executed")
    input_hash: str = Field(description="SHA256 hash of input data")
    output_hash: str = Field(description="SHA256 hash of output data")
    latency_ms: float = Field(description="Execution time in milliseconds")
    deterministic: bool = Field(
        description="Flag indicating deterministic execution (always True)"
    )


class TaskResult(BaseModel):
    """Result of a single task execution."""

    task_id: str = Field(description="Task identifier")
    output: Any = Field(description="Task output data")
    log: ExecutionLog = Field(description="Execution log")


class WorkflowResult(BaseModel):
    """Result of workflow execution."""

    workflow_id: str = Field(description="Workflow identifier")
    final_output: Any = Field(description="Final workflow output")
    execution_logs: List[ExecutionLog] = Field(
        description="Execution logs for all tasks"
    )
    total_latency_ms: float = Field(description="Total workflow execution time")
