"""MCP Tool Registry — central tool discovery and validation.

Single source of truth for all available tools.
Enforces:
- Unique tool names
- Schema validity
- Deterministic operation
"""

from typing import Dict, List, Optional
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest


class DuplicateToolError(Exception):
    """Attempted to register tool with duplicate name."""
    pass


class ToolNotFoundError(Exception):
    """Attempted to get tool that is not registered."""
    pass


class MCPRegistry:
    """Global registry of all available MCP tools.
    
    Thread-safe operations. Read-heavy (tools don't change during execution).
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, MCPTool] = {}
    
    def register(self, tool: MCPTool) -> None:
        """
        Register a tool.
        
        Args:
            tool: MCPTool instance
        
        Raises:
            DuplicateToolError: If tool name already registered
            ValueError: If manifest is invalid
        """
        manifest = tool.manifest()
        
        # Validate manifest
        if not manifest.name:
            raise ValueError("Tool name cannot be empty")
        
        # Check for duplicates
        if manifest.name in self._tools:
            raise DuplicateToolError(f"Tool '{manifest.name}' already registered")
        
        # Register
        self._tools[manifest.name] = tool
    
    def get(self, name: str) -> MCPTool:
        """
        Retrieve a registered tool.
        
        Args:
            name: Tool name
        
        Returns:
            MCPTool instance
        
        Raises:
            ToolNotFoundError: If tool not registered
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return self._tools[name]
    
    def list_manifests(self) -> List[MCPManifest]:
        """
        Get manifests for all registered tools.
        
        Returns:
            List of MCPManifest objects in registration order
        """
        return [tool.manifest() for tool in self._tools.values()]
    
    def has(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools
    
    def list_names(self) -> List[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())
    
    def get_manifest(self, name: str) -> MCPManifest:
        """
        Get manifest for a specific tool without executing it.
        
        Args:
            name: Tool name
        
        Returns:
            MCPManifest for the tool
        
        Raises:
            ToolNotFoundError: If tool not found
        """
        tool = self.get(name)
        return tool.manifest()
    
    def list_tools(self) -> List[str]:
        """Get all registered tool names (alias for list_names for compatibility).
        
        Returns:
            List of tool names
        """
        return self.list_names()
    
    def validate_pipeline(self, pipeline: List[str]) -> None:
        """
        Validate that all tools in a pipeline are registered.
        
        Args:
            pipeline: List of tool names in execution order
        
        Raises:
            ToolNotFoundError: If any tool not found
            ValueError: If pipeline is empty or has duplicates
        """
        if not pipeline:
            raise ValueError("Pipeline cannot be empty")
        
        if len(pipeline) != len(set(pipeline)):
            raise ValueError(f"Pipeline has duplicate tool names: {pipeline}")
        
        for tool_name in pipeline:
            if not self.has(tool_name):
                raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")
