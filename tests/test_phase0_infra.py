from pathlib import Path

from core.mcp.mcp_manifest import MCPManifest
from core.mcp.mcp_tool import MCPTool
from core.mcp.trace import ExecutionTrace, TraceEntry


ROOT = Path(__file__).resolve().parents[1]


def test_phase0_deliverables_exist() -> None:
    required_paths = [
        ROOT / ".env.template",
        ROOT / "infra" / "docker" / "docker-compose.yml",
        ROOT / "infra" / "config" / ".env.template",
        ROOT / "core" / "mcp" / "mcp_tool.py",
        ROOT / "core" / "mcp" / "mcp_manifest.py",
        ROOT / "core" / "mcp" / "trace.py",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing Phase 0 deliverable: {path}"


def test_compose_defines_local_first_services() -> None:
    compose_text = (ROOT / "infra" / "docker" / "docker-compose.yml").read_text()

    assert "chroma:" in compose_text
    assert "redis:" in compose_text
    assert "ollama:" in compose_text
    assert ".local/chroma" in compose_text
    assert ".local/redis" in compose_text
    assert ".local/ollama" in compose_text


def test_env_template_defines_phase0_runtime_variables() -> None:
    env_text = (ROOT / ".env.template").read_text()

    required_vars = [
        "VECTOR_STORE_URL=",
        "METADATA_DB_PATH=",
        "TRACE_STORE_PATH=",
        "OLLAMA_MODEL=",
        "EMBEDDING_MODEL=",
        "REDIS_HOST=",
        "CHROMA_PORT=",
    ]

    for variable in required_vars:
        assert variable in env_text


def test_mcp_phase0_primitives_are_importable() -> None:
    assert issubclass(MCPTool, object)
    assert MCPManifest.__name__ == "MCPManifest"
    assert ExecutionTrace.__name__ == "ExecutionTrace"
    assert TraceEntry.__name__ == "TraceEntry"
