# Infrastructure Layer

This directory contains local-first runtime infrastructure and service wiring.

Contents:
- docker/: compose files and image build configuration
- config/: environment templates and runtime configuration

Constraints:
- Local-first execution
- Reproducible setup
- No cloud-only assumptions

## Phase 0 Deliverables

- Docker Compose stack: `infra/docker/docker-compose.yml`
- Canonical environment template: `.env.template`
- Infra-specific environment template: `infra/config/.env.template`
- MCP base interface: `core/mcp/mcp_tool.py`
- MCP manifest schema: `core/mcp/mcp_manifest.py`
- Execution trace schema: `core/mcp/trace.py`

## Local Services

Phase 0 provisions the baseline local dependencies required by later phases:
- Chroma for vector retrieval
- Redis for session state
- Ollama for local model execution
- SQLite and JSON trace storage on the host filesystem

## Startup

1. Copy `.env.template` to `.env`
2. Start local services with `docker compose -f infra/docker/docker-compose.yml --env-file .env up -d`
3. Keep SQLite and trace files under `.local/`

This layer is intentionally infrastructure-only. Service API containers are added in later phases.
