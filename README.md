# Researcher-AI

Researcher‑AI is an evidence‑first research assistance platform that combines deterministic tooling, selective multi‑agent reasoning, and explicit provenance to accelerate and structure the academic research lifecycle.

> Designed to think with researchers — mapping literature, extracting evidence, generating + critiquing hypotheses, and producing reproducible artifacts.

## What it is

Researcher‑AI is not a generic chatbot. It's a workflow system for researchers that emphasizes:

- Traceability: every claim links back to source snippets and trace metadata.
- Modularity: small, testable tool services communicate via a common MCP interface.
- Selective agentic reasoning: agent-to-agent critique is used only when it adds value.

## Key Features

- Semantic literature mapping and cluster labeling
- Claim extraction and contradiction detection with provenance
- Iterative hypothesis generation + critic loops with confidence scoring
- Multimodal evidence extraction (tables, figures, captions) → structured outputs
- Proposal & artifact generation with explicit citations and rationale

## Architecture (summary)

Core components:

- `Orchestrator`: task planning, session management, trace aggregation
- `MCP Tool Services`: ingestion, RAG, mapping, extraction, artifact generation (FastAPI)
- `Agents`: Hypothesis, Critic, and task‑specific reasoners communicating via MCP

See `docs/architecture.md` and `docs/components.md` for full details and interfaces.

## Quick conceptual setup

1. Start core services (ingestion, RAG/vector DB, mapping, extraction, orchestrator).
2. Configure the orchestrator with MCP manifests for each service.
3. Ingest a seed corpus and index embeddings.
4. Run mapping → hypothesis generation → critic loop → extraction → artifact generation.

## Developer notes

- Implement services as small FastAPI apps exposing `GET /manifest` and `POST /call`.
- Use unit tests for deterministic services and integration tests with mocked LLMs for agent loops.
- Keep prompt templates and schemas under version control.

## Example MCP call (ingest)

Request to `POST /call` on `ingestion-service`:

```json
{
	"operation": "ingest_pdf",
	"inputs": {"pdf_base64": "..."},
	"session_id": "sess-123"
}
```

Response (minimal):

```json
{
	"status": "ok",
	"outputs": {"document_id":"doc-123","chunks":42},
	"trace": {"service_version":"0.1.0","timestamp":"..."}
}
```

## Running locally (suggested)

- Provide a `docker-compose.yml` that launches the minimal stack: ingestion, RAG/Chroma, mapping, extraction, orchestrator.
- For tests, use small local LLMs or a hosted provider; ensure trace logging is enabled and prompt templates are tested.

## Tests & evaluation

- Unit test deterministic tools (parsing, extraction, embedding pipeline).
- Integration tests for end‑to‑end flows using a tiny corpus and mocked agent LLM responses.

## Contributing

See `docs/contributing.md`. Helpful contributions:

- Add MCP manifests for tools.
- Implement deterministic services and tests.
- Add deployment manifests and operator runbooks.

---

If you want, I can add a `docker-compose.yml`, minimal service stubs, or an SVG architecture diagram in `docs/`.
