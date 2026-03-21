"""Runtime metrics collector for ScholarOS pipeline observability.

Collects latency, token usage, claim yield, and cache hit statistics
across pipeline executions.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolMetrics:
    """Metrics for a single tool invocation."""

    tool: str
    duration_ms: float
    status: str
    input_hash: str = ""
    output_hash: str = ""
    tokens_used: Optional[int] = None
    cache_hit: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionMetrics:
    """Aggregated metrics for a complete session."""

    session_id: str
    total_duration_ms: float = 0.0
    step_count: int = 0
    error_count: int = 0
    claim_count: int = 0
    chunk_count: int = 0
    total_tokens: int = 0
    cache_hits: int = 0
    tool_latencies: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))


class MetricsCollector:
    """Collects and aggregates runtime metrics for pipeline observability.

    Thread-safe in-process metrics collection.
    Designed for single-process use; use Prometheus/OpenTelemetry for distributed.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionMetrics] = {}
        self._tool_invocations: List[ToolMetrics] = []
        self._start_time = time.time()

    def record_tool_invocation(
        self,
        session_id: str,
        tool: str,
        duration_ms: float,
        status: str,
        input_hash: str = "",
        output_hash: str = "",
        tokens_used: Optional[int] = None,
        cache_hit: bool = False,
    ) -> None:
        """Record a single tool invocation.

        Args:
            session_id: Session identifier
            tool: Tool name
            duration_ms: Execution time in milliseconds
            status: 'success' or 'error'
            input_hash: SHA256 of input payload
            output_hash: SHA256 of output payload
            tokens_used: Token count for LLM-backed tools
            cache_hit: Whether result came from cache
        """
        metric = ToolMetrics(
            tool=tool,
            duration_ms=duration_ms,
            status=status,
            input_hash=input_hash,
            output_hash=output_hash,
            tokens_used=tokens_used,
            cache_hit=cache_hit,
        )
        self._tool_invocations.append(metric)

        session = self._sessions.setdefault(
            session_id,
            SessionMetrics(session_id=session_id),
        )
        session.step_count += 1
        session.total_duration_ms += duration_ms
        if status == "error":
            session.error_count += 1
        if tokens_used:
            session.total_tokens += tokens_used
        if cache_hit:
            session.cache_hits += 1
        session.tool_latencies[tool].append(duration_ms)

    def record_claims(self, session_id: str, claim_count: int) -> None:
        """Record claim extraction yield."""
        session = self._sessions.setdefault(session_id, SessionMetrics(session_id=session_id))
        session.claim_count += claim_count

    def record_chunks(self, session_id: str, chunk_count: int) -> None:
        """Record chunk count for yield computation."""
        session = self._sessions.setdefault(session_id, SessionMetrics(session_id=session_id))
        session.chunk_count += chunk_count

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of metrics for a session.

        Returns:
            Dict with duration, step_count, claim_yield, avg_latency, etc.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return {"session_id": session_id, "found": False}

        claim_yield = (
            session.claim_count / session.chunk_count
            if session.chunk_count > 0
            else 0.0
        )

        avg_latencies = {
            tool: sum(lats) / len(lats)
            for tool, lats in session.tool_latencies.items()
            if lats
        }

        return {
            "session_id": session_id,
            "found": True,
            "total_duration_ms": round(session.total_duration_ms, 1),
            "step_count": session.step_count,
            "error_count": session.error_count,
            "claim_count": session.claim_count,
            "chunk_count": session.chunk_count,
            "claim_yield": round(claim_yield, 4),
            "total_tokens": session.total_tokens,
            "cache_hits": session.cache_hits,
            "avg_latency_by_tool": {k: round(v, 1) for k, v in avg_latencies.items()},
        }

    def get_global_summary(self) -> Dict[str, Any]:
        """Get global metrics across all sessions."""
        total_invocations = len(self._tool_invocations)
        errors = sum(1 for m in self._tool_invocations if m.status == "error")
        cache_hits = sum(1 for m in self._tool_invocations if m.cache_hit)

        tool_counts: Dict[str, int] = defaultdict(int)
        tool_durations: Dict[str, float] = defaultdict(float)
        for m in self._tool_invocations:
            tool_counts[m.tool] += 1
            tool_durations[m.tool] += m.duration_ms

        return {
            "total_invocations": total_invocations,
            "error_rate": round(errors / max(total_invocations, 1), 4),
            "cache_hit_rate": round(cache_hits / max(total_invocations, 1), 4),
            "total_sessions": len(self._sessions),
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "per_tool": {
                tool: {
                    "invocations": tool_counts[tool],
                    "avg_ms": round(tool_durations[tool] / tool_counts[tool], 1),
                }
                for tool in tool_counts
            },
        }

    def from_trace_entries(self, session_id: str, entries: List[Dict]) -> None:
        """Populate metrics from existing trace entries.

        Args:
            session_id: Session identifier
            entries: List of trace entry dicts
        """
        for entry in entries:
            self.record_tool_invocation(
                session_id=session_id,
                tool=entry.get("tool", ""),
                duration_ms=entry.get("duration_ms", 0.0),
                status=entry.get("status", "unknown"),
                input_hash=entry.get("input_hash", ""),
                output_hash=entry.get("output_hash", ""),
                tokens_used=entry.get("token_usage", {}).get("total") if entry.get("token_usage") else None,
            )


# Module-level singleton for convenience
_global_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """Get the global metrics collector singleton."""
    return _global_collector
