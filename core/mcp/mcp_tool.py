"""MCP Tool Abstract Base Class — protocol enforcement.

Every service that participates in the orchestration pipeline
must implement this interface.

This ensures:
- All tools are discoverable
- All tools are self-describing
- All tools have explicit input/output contracts
- All tools are deterministic
- No tool relies on hidden state
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from core.mcp.mcp_manifest import MCPManifest


class MCPTool(ABC):
    """Abstract base class for all MCP tools.
    
    Subclasses must implement:
    - manifest() — returns MCPManifest describing the tool
    - call(payload) — executes the tool with explicit input dict
    
    Constraints for all implementations:
    - No global state access
    - No side effects beyond logging
    - No imports of other services except own internal service
    - All state passed through payload dicts
    - Deterministic output for identical inputs
    """

    @abstractmethod
    def manifest(self) -> MCPManifest:
        """
        Return the tool manifest.
        
        This describes:
        - What the tool does
        - What inputs it accepts
        - What outputs it produces
        - Whether it's deterministic
        
        Called during registry initialization and inspection.
        
        Returns:
            MCPManifest describing this tool
        """
        pass

    @abstractmethod
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with explicit input payload.
        
        Args:
            payload: Input dict matching input_schema from manifest
        
        Returns:
            Output dict matching output_schema from manifest
            
        Raises:
            ValueError: If payload does not match input_schema
            RuntimeError: If tool execution fails
        
        Constraints:
        - Must not modify input payload
        - Must not access instance state except manifest metadata
        - Must be deterministic (same payload → same output every time)
        - Must not import other services
        """
        pass
