"""DAG definitions and topological sort for orchestrator workflows.

Supports conditional branching and parallel execution planning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class DAGNode:
    """Single node in a DAG execution graph."""

    task_id: str
    tool: str
    depends_on: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    parallel_group: Optional[str] = None


@dataclass
class DAGDefinition:
    """A directed acyclic graph of tool executions."""

    dag_id: str
    nodes: Dict[str, DAGNode] = field(default_factory=dict)

    def add_node(self, node: DAGNode) -> None:
        if node.task_id in self.nodes:
            raise ValueError(f"Duplicate task_id: {node.task_id}")
        self.nodes[node.task_id] = node

    def validate(self) -> List[str]:
        """Validate DAG structure. Returns list of errors (empty = valid)."""
        errors = []
        for task_id, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    errors.append(f"Task '{task_id}' depends on unknown task '{dep}'")

        # Check for cycles
        if not errors and self._has_cycle():
            errors.append("DAG contains a cycle")

        return errors

    def _has_cycle(self) -> bool:
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for dep in self.nodes[node_id].depends_on:
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def topological_sort(self) -> List[str]:
        """Return task IDs in valid execution order."""
        in_degree: Dict[str, int] = {tid: 0 for tid in self.nodes}
        for node in self.nodes.values():
            for dep in node.depends_on:
                # dep must complete before node, so node has in-degree from dep
                pass
            in_degree[node.task_id] = len(node.depends_on)

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        queue.sort()  # Deterministic ordering
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            for tid, node in self.nodes.items():
                if current in node.depends_on:
                    in_degree[tid] -= 1
                    if in_degree[tid] == 0:
                        # Insert sorted for determinism
                        queue.append(tid)
                        queue.sort()

        if len(result) != len(self.nodes):
            raise ValueError("DAG contains a cycle — cannot produce topological sort")

        return result

    def get_parallel_groups(self) -> List[List[str]]:
        """Group tasks that can execute in parallel (same depth level)."""
        order = self.topological_sort()
        depths: Dict[str, int] = {}

        for tid in order:
            node = self.nodes[tid]
            if not node.depends_on:
                depths[tid] = 0
            else:
                depths[tid] = max(depths[dep] for dep in node.depends_on) + 1

        max_depth = max(depths.values()) if depths else 0
        groups = []
        for d in range(max_depth + 1):
            group = sorted(tid for tid, depth in depths.items() if depth == d)
            if group:
                groups.append(group)

        return groups
