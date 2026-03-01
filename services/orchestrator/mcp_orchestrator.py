"""MCP Orchestrator — deterministic pipeline execution.

Executes tools in sequence, passing output to next input.
No reasoning, no branching, no LLM calls.
Only deterministic tool invocation.

Logs complete trace for reproducibility verification.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import uuid

from core.mcp.registry import MCPRegistry, ToolNotFoundError
from core.mcp.trace import ExecutionTrace, TraceEntry, hash_payload


class MCPOrchestrator:
    """Deterministic pipeline orchestrator.
    
    Executes a pre-defined list of tools in sequence.
    No control flow, no branching, no implicit dependencies.
    All state is passed through payloads.
    """
    
    def __init__(self, registry: MCPRegistry):
        """
        Initialize orchestrator with tool registry.
        
        Args:
            registry: MCPRegistry containing all available tools
        """
        self._registry = registry
    
    def execute_pipeline(
        self,
        pipeline: List[str],
        initial_payload: Dict[str, Any]
    ) -> ExecutionTrace:
        """
        Execute pipeline: invoke tools in sequence.
        
        Args:
            pipeline: Ordered list of tool names
            initial_payload: Starting input dict
        
        Returns:
            ExecutionTrace with full provenance and final output
        
        Raises:
            ToolNotFoundError: If any tool not found
            RuntimeError: If any tool execution fails
            ValueError: If pipeline invalid
        """
        # Validate pipeline
        self._registry.validate_pipeline(pipeline)
        
        # Initialize execution
        session_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()
        trace_entries: List[TraceEntry] = []
        current_payload = initial_payload.copy()
        
        # Execute each tool
        for sequence, tool_name in enumerate(pipeline):
            # Get tool
            try:
                tool = self._registry.get(tool_name)
            except ToolNotFoundError as e:
                raise RuntimeError(f"Execution failed at step {sequence}: {str(e)}")
            
            # Hash input
            input_hash = hash_payload(current_payload)
            
            # Execute tool
            step_start = time.time()
            try:
                result = tool.call(current_payload)
                status = "success"
                error_msg = None
            except Exception as e:
                status = "error"
                error_msg = str(e)
                result = {}
            
            step_duration = (time.time() - step_start) * 1000  # ms
            
            # Hash output
            output_hash = hash_payload(result)
            
            # Record trace entry
            trace_entries.append(TraceEntry(
                sequence=sequence,
                tool=tool_name,
                input_hash=input_hash,
                output_hash=output_hash,
                timestamp=datetime.utcnow(),
                status=status,
                error_message=error_msg,
                duration_ms=step_duration
            ))
            
            # Stop on error
            if status == "error":
                raise RuntimeError(
                    f"Tool '{tool_name}' failed at step {sequence}: {error_msg}"
                )
            
            # Pass result to next tool
            current_payload = result
        
        # Create final trace
        completed_at = datetime.utcnow()
        final_output_hash = hash_payload(current_payload)
        
        trace = ExecutionTrace(
            session_id=session_id,
            started_at=started_at,
            completed_at=completed_at,
            entries=trace_entries,
            final_output_hash=final_output_hash,
            final_output=current_payload,
            pipeline_definition=pipeline
        )
        
        return trace
    
    def validate_pipeline(self, pipeline: List[str]) -> bool:
        """
        Check if pipeline can execute (all tools exist).
        
        Args:
            pipeline: List of tool names
        
        Returns:
            True if valid, False otherwise
        """
        try:
            self._registry.validate_pipeline(pipeline)
            return True
        except (ValueError, ToolNotFoundError):
            return False
