"""Phase 4 tests for MCP orchestrator runtime guarantees.

Covers:
- schema-bound payload pruning
- bounded retries for transient failures
- no retry for fatal failures
- session phase tracking
- local JSON trace persistence
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.mcp.mcp_manifest import MCPManifest
from core.mcp.mcp_tool import MCPTool
from core.mcp.registry import MCPRegistry
from core.mcp.trace import JSONTraceStore
from services.orchestrator.mcp_orchestrator import InMemorySessionStore, MCPOrchestrator


class _EchoTool(MCPTool):
    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="echo",
            version="1.0.0",
            description="Echo selected fields",
            input_schema={
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
            },
            deterministic=True,
        )

    def call(self, payload):
        return {"value": payload["value"]}


class _FlakyTool(MCPTool):
    def __init__(self, *, fail_count: int, message: str):
        self._fail_count = fail_count
        self._message = message
        self.calls = 0

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="flaky",
            version="1.0.0",
            description="Fails a fixed number of times then succeeds",
            input_schema={
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
            },
            deterministic=True,
        )

    def call(self, payload):
        self.calls += 1
        if self.calls <= self._fail_count:
            raise RuntimeError(self._message)
        return {"value": payload["value"]}


def _build_orchestrator(tmp_path: Path, tools: list[MCPTool]):
    registry = MCPRegistry()
    for tool in tools:
        registry.register(tool)
    session_store = InMemorySessionStore()
    trace_store = JSONTraceStore(base_dir=str(tmp_path / "traces"))
    orch = MCPOrchestrator(registry, session_store=session_store, trace_store=trace_store)
    return orch, session_store


def test_payload_is_pruned_to_manifest_schema(tmp_path: Path):
    orch, _ = _build_orchestrator(tmp_path, [_EchoTool()])

    trace = orch.execute_pipeline(
        ["echo"],
        {"value": "ok", "extra": "should_be_pruned"},
        user_input="phase4 test",
    )

    assert trace.final_output == {"value": "ok"}
    assert trace.entries[0].status == "success"


def test_missing_required_field_raises_schema_error(tmp_path: Path):
    orch, _ = _build_orchestrator(tmp_path, [_EchoTool()])

    with pytest.raises(ValueError, match="missing required fields"):
        orch.execute_pipeline(["echo"], {"extra": "x"}, user_input="phase4 test")


def test_transient_error_retries_and_then_succeeds(tmp_path: Path):
    flaky = _FlakyTool(fail_count=2, message="timeout while calling upstream")
    orch, _ = _build_orchestrator(tmp_path, [flaky])

    trace = orch.execute_pipeline(["flaky"], {"value": "ok"}, user_input="phase4 test")

    assert flaky.calls == 3
    assert trace.entries[-1].status == "success"
    assert [e.attempt for e in trace.entries] == [1, 2, 3]


def test_fatal_error_does_not_retry(tmp_path: Path):
    flaky = _FlakyTool(fail_count=1, message="invalid schema payload")
    orch, _ = _build_orchestrator(tmp_path, [flaky])

    with pytest.raises(RuntimeError, match="failed at step"):
        orch.execute_pipeline(["flaky"], {"value": "ok"}, user_input="phase4 test")

    assert flaky.calls == 1


def test_session_phase_updated_and_trace_persisted(tmp_path: Path):
    orch, session_store = _build_orchestrator(tmp_path, [_EchoTool()])

    trace = orch.execute_pipeline(
        ["echo"],
        {"value": "ok"},
        session_id="sess-phase4",
        user_input="phase4 test",
        phase_labels={"echo": "ingestion"},
    )

    session = session_store.get("sess-phase4")
    assert session is not None
    assert session.phase == "ingestion"

    traces_dir = tmp_path / "traces"
    persisted = list(traces_dir.glob("trace_sess-phase4_*.json"))
    assert len(persisted) == 1
    assert persisted[0].read_text(encoding="utf-8")
    assert trace.session_id == "sess-phase4"
