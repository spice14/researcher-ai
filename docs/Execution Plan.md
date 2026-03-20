# ScholarOS — E2E Execution Plan to Completion

## Context

ScholarOS is an agentic research assistant with 5 locked capabilities (Literature Mapping, Contradiction/Consensus, Hypothesis/Critique, Multimodal Extraction, Proposal Generation). The architecture is sound — 14 schemas, 15 validators, 10 MCP-wrapped services, 2 LLM-backed agents, bounded iteration loop, MCP orchestrator, Docker infra, 41 test files, CI pipeline. However, **3 of 5 capabilities are <30% implemented**, critical data stores are missing, agents aren't wired into the pipeline, and there's no user-facing interface.

**Source of truth:** [README.md](README.md), [capabilities.md](capabilities.md), [Design.md](Design.md)

**Goal:** Close all gaps to deliver a fully functional system with all 5 capabilities operational, persistent storage, human-in-the-loop interaction, and comprehensive evaluation.

---

## Phase 0: Data Layer Foundation (5-7 days)

**Goal:** Establish persistent vector and metadata storage as MCP-wrapped services.

### Create

| File | Purpose |
|------|---------|
| `services/vectorstore/service.py` | Chroma client: `add_embeddings()`, `query()`, `delete()` against Docker container |
| `services/vectorstore/tool.py` | MCP wrapper: manifest `vector_store`, ops `add`/`query`/`delete` |
| `services/vectorstore/schemas.py` | `VectorAddRequest`, `VectorQueryRequest`, `VectorQueryResult` |
| `services/metadatastore/service.py` | SQLite wrapper: `save_paper()`, `get_paper()`, `save_claims()`, `get_claims()`, `save_session()` |
| `services/metadatastore/tool.py` | MCP wrapper: manifest `metadata_store` |
| `services/metadatastore/schemas.py` | Store request/response schemas |
| `services/metadatastore/migrations.py` | DDL: tables for papers, sessions, claims, hypotheses, proposals |
| `services/embedding/service.py` | Wraps `sentence-transformers/all-MiniLM-L6-v2` or Ollama embeddings endpoint |
| `services/embedding/tool.py` | MCP wrapper: manifest `embedding`, op `embed` |
| `services/embedding/schemas.py` | `EmbeddingRequest`, `EmbeddingResult` |
| `tests/test_vectorstore_service.py` | Chroma CRUD + MCP contract tests |
| `tests/test_metadatastore_service.py` | SQLite CRUD + persistence tests |
| `tests/test_embedding_service.py` | Embedding dimension + determinism tests |

### Modify

| File | Change |
|------|--------|
| `requirements.txt` | Add `chromadb>=0.5.0`, `sentence-transformers>=2.2.0` |
| `infra/docker/docker-compose.yml` | Already has Chroma/Redis/Ollama — verify ports match .env |

### Success Criteria
- Vector add + query round-trips against Chroma container
- SQLite data survives process restart
- Embedding service returns 384-dim vectors
- All 3 new tools pass MCP contract enforcement tests

### Dependencies: None

---

## Phase 1: Service Hardening (8-10 days)

**Goal:** Upgrade RAG to semantic retrieval, improve claim extraction yield from 3.27% to 15%+, wire all services into unified DAG-based pipeline.

### Modify

| File | Change |
|------|--------|
| `services/rag/service.py` | Replace lexical overlap with Chroma vector query; fall back to lexical when unavailable |
| `services/rag/tool.py` | Inject `VectorStoreService` + `EmbeddingService`; `corpus` param becomes optional |
| `services/extraction/service.py` | (a) Loosen `_is_hedged_statement` for numeric signals, (b) Add comparative claim path ("X outperforms Y by Z%"), (c) Expand `_IMPLICIT_METRIC_OF`, (d) Add bounded LLM-assisted extraction fallback for chunks with metric+number but no matched predicate |
| `services/ingestion/service.py` | After chunking, call EmbeddingService + VectorStoreService to persist embeddings |
| `services/orchestrator/mcp_orchestrator.py` | Add `execute_dag()`: accepts DAG definition (dict of task_id -> {tool, depends_on, params}), topological sort execution |
| `services/orchestrator/workflows.py` | Add `FULL_ANALYSIS` workflow with placeholders for mapping and agent steps |

### Create

| File | Purpose |
|------|---------|
| `services/orchestrator/dag.py` | `DAGDefinition`, `DAGNode`, topological sort, conditional branch support |
| `tests/test_semantic_rag.py` | Semantic retrieval tests with mocked Chroma |
| `tests/test_extraction_yield.py` | Golden test: assert claim count >= 50/paper on 5 reference papers |
| `tests/test_dag_orchestrator.py` | DAG execution + conditional branching tests |

### Success Criteria
- RAG returns semantic matches with cosine scores > 0.5
- Extraction yield >= 8% on corpus (up from 3.27%)
- DAG orchestrator runs 3-node graph with conditional branch
- `FULL_ANALYSIS` workflow runs end-to-end on single paper
- Existing MCP contract tests still pass

### Dependencies: Phase 0

---

## Phase 2: Contextual Literature Mapping — CAP 1 (6-8 days)

**Goal:** Deliver full Capability 1: semantic retrieval + HDBSCAN clustering + LLM labeling + structured `ClusterMap` output.

### Create

| File | Purpose |
|------|---------|
| `services/mapping/service.py` | `LiteratureMappingService`: query Chroma → aggregate to paper embeddings → HDBSCAN → identify representative/boundary papers → LLM label clusters → return `ClusterMap` |
| `services/mapping/tool.py` | MCP wrapper: manifest `mapping`, op `build_map` |
| `services/mapping/schemas.py` | `MappingRequest`, `MappingResult` |
| `services/mapping/clusterer.py` | HDBSCAN wrapper with deterministic seed |
| `services/mapping/labeler.py` | LLM cluster labeler with versioned prompt |
| `tests/test_mapping_service.py` | Synthetic embeddings + mocked Chroma |
| `tests/test_hdbscan_clustering.py` | Clustering determinism and edge cases |

### Modify

| File | Change |
|------|--------|
| `requirements.txt` | Add `hdbscan>=0.8.33`, `numpy>=1.24.0`, `scikit-learn>=1.3.0` |
| `core/schemas/cluster_map.py` | Add `paper_count`, `noise_paper_ids`, `similarity_score` fields |
| `core/llm/prompts.py` | Add `CLUSTER_LABEL_PROMPT` + version |
| `services/orchestrator/workflows.py` | Replace mapping placeholder with real `mapping` tool |

### Success Criteria
- 20+ papers → ClusterMap with >= 2 non-noise clusters
- Each cluster has non-empty LLM-generated label
- Representative + boundary papers identified per cluster
- Deterministic: same embeddings → same clusters
- ClusterMap passes validator

### Dependencies: Phase 1

---

## Phase 3: Agent Completion — CAP 3 (7-9 days)

**Goal:** Wire agents into orchestrator with semantic evidence retrieval, convergence detection, confidence rationale, and pause/resume.

### Create

| File | Purpose |
|------|---------|
| `services/agent_loop/tool.py` | MCP wrapper for hypothesis-critique loop |
| `services/agent_loop/schemas.py` | `AgentLoopRequest`, `AgentLoopResult` |
| `services/consolidation/service.py` | Takes loop result + beliefs + clusters → structured analysis summary |
| `services/consolidation/tool.py` | MCP wrapper: manifest `consolidation` |
| `services/consolidation/schemas.py` | `ConsolidationRequest`, `ConsolidationResult` |
| `tests/test_agent_loop_tool.py` | MCP contract tests |
| `tests/test_consolidation_service.py` | Unit tests |
| `tests/test_convergence_detection.py` | Convergence behavior tests |

### Modify

| File | Change |
|------|--------|
| `agents/loop.py` | Add convergence detection (delta < threshold for 2 iterations → stop), user intervention points, confidence rationale in trace |
| `agents/hypothesis/agent.py` | Parse `confidence_rationale` from LLM, wire supporting/contradicting claims |
| `agents/critic/agent.py` | Accept RAG matches directly, add severity rationale |
| `core/schemas/hypothesis.py` | Add `confidence_rationale: Optional[str]` |
| `core/schemas/critique.py` | Add `confidence_rationale: Optional[str]` |
| `core/llm/prompts.py` | Update prompts to request rationale; bump versions to v1.1.0 |
| `services/orchestrator/workflows.py` | Add `hypothesis_critique_loop` → `consolidation` after belief step |
| `services/orchestrator/mcp_orchestrator.py` | Add `pause_at` support + `resume_pipeline()` method |

### Success Criteria
- Agent loop produces `LoopResult` with non-null `final_hypothesis`
- Loop converges in <= 5 iterations
- `confidence_rationale` non-empty in outputs
- `pause_at` causes pipeline to pause; `resume_pipeline()` continues
- Consolidation produces structured summary
- Full pipeline runs end-to-end through consolidation

### Dependencies: Phase 1 (semantic RAG), Phase 2 (mapping feeds agent context)

---

## Phase 4: Multimodal + Proposal — CAP 4, 5 (7-9 days)

**Goal:** Integrate multimodal extraction into pipeline and upgrade proposal service with LLM-backed generation and LaTeX export.

### Modify

| File | Change |
|------|--------|
| `services/multimodal/service.py` | Add `extract_from_pdf()` using PyMuPDF table parsing, link extracted metrics to claim IDs |
| `services/multimodal/tool.py` | Add `pdf_path` input, `link_to_claims` option |
| `services/proposal/service.py` | Add `LLMProposalService`: Ollama-backed novelty/methodology/outcomes generation, accept evidence_tables |
| `services/proposal/tool.py` | Add `use_llm`, `export_format` (md/latex), `evidence_tables` params |
| `services/proposal/schemas.py` | Add `evidence_tables`, `latex_output` fields |
| `core/llm/prompts.py` | Add proposal section prompts with versions |
| `services/orchestrator/workflows.py` | Add multimodal (parallel) and proposal (final) steps |

### Create

| File | Purpose |
|------|---------|
| `services/proposal/latex_renderer.py` | LaTeX template rendering with citation formatting |
| `services/proposal/llm_sections.py` | LLM-backed section generators with versioned prompts |
| `tests/test_multimodal_integration.py` | PDF-based extraction + claim linking tests |
| `tests/test_proposal_llm.py` | LLM-backed generation tests (mocked Ollama) |
| `tests/test_latex_renderer.py` | LaTeX output validity tests |

### Success Criteria
- Multimodal extracts >= 1 table from table-containing PDF
- Extracted metrics link to claim IDs
- LLM-backed proposal produces richer content than deterministic baseline
- LaTeX export compiles
- Full pipeline produces proposal with embedded evidence tables

### Dependencies: Phase 3 (consolidation provides hypothesis for proposal)

---

## Phase 5: Human-in-the-Loop Interface (5-7 days)

**Goal:** CLI tool for researchers to submit papers, inspect results, pause/resume, browse provenance.

### Create

| File | Purpose |
|------|---------|
| `cli/app.py` | Main CLI: `ingest`, `analyze`, `map`, `hypothesize`, `propose`, `status`, `inspect`, `trace`, `resume`, `papers`, `claims`, `export` |
| `cli/runner.py` | Pipeline setup: registry, tool registration, orchestrator, session management |
| `cli/inspector.py` | Provenance browser: trace backward from output → claim → chunk → paper |
| `cli/formatters.py` | Terminal output formatters for ClusterMap, ContradictionReport, Hypothesis, Proposal |
| `tests/test_cli_commands.py` | CLI parsing + dispatch tests |
| `tests/test_cli_runner.py` | Integration tests |

### Modify

| File | Change |
|------|--------|
| `core/schemas/session.py` | Add `paused`, `paused_at_tool`, `intermediate_outputs` fields |

### Success Criteria
- `python -m cli.app ingest <pdf>` ingests and prints chunk count
- `python -m cli.app analyze <paper_id>` runs full pipeline
- `python -m cli.app analyze --pause-at hypothesis_critique_loop` pauses, `resume` continues
- `python -m cli.app trace <session_id>` prints provenance chain
- Graceful degradation without Docker (lexical RAG fallback)

### Dependencies: Phase 4

---

## Phase 6: Evaluation, Observability & Polish (6-8 days)

**Goal:** Ground truth, comprehensive metrics, provenance audit, CI hardening.

### Create

| File | Purpose |
|------|---------|
| `evaluation/annotation_schema.py` | Ground truth schema: annotated claims, clusters, contradictions |
| `evaluation/metrics.py` | Claim P/R/F1, cluster purity/NMI, hypothesis quality scoring |
| `evaluation/benchmark_runner.py` | Batch eval: run pipeline on corpus, compute metrics, generate report |
| `evaluation/ground_truth/annotated_5papers.jsonl` | Initial 5-paper annotation |
| `core/observability/metrics_collector.py` | Runtime metrics: latency, tokens, yield, cache hits |
| `core/observability/provenance_audit.py` | Chain validator: proposal → hypothesis → claims → chunks → paper |
| `tests/test_provenance_audit.py` | Provenance integrity tests |
| `tests/test_evaluation_metrics.py` | Metric computation correctness tests |

### Modify

| File | Change |
|------|--------|
| `.github/workflows/repo-hygiene.yml` | Add full test suite, type checking, 3-paper benchmark regression |
| `scripts/e2e_test_harness.py` | Use evaluation metrics against ground truth |

### Success Criteria
- Claim extraction F1 >= 0.40 on 5-paper ground truth
- Cluster purity >= 0.60 on 20-paper set
- Provenance audit: 100% of proposal citations trace to valid chunks
- CI runs full suite + benchmark regression in < 5 minutes
- Every tool invocation produces trace with `input_hash`, `output_hash`, `duration_ms`

### Dependencies: All phases; ground truth annotation starts during Phase 2

---

## Dependency Chain

```
Phase 0 (Data Layer)
    │
    v
Phase 1 (Service Hardening)
    │
    ├──> Phase 2 (Literature Mapping / CAP 1)
    │        │
    │        v
    └──> Phase 3 (Agent Completion / CAP 3)
              │
              v
         Phase 4 (Multimodal + Proposal / CAP 4, 5)
              │
              v
         Phase 5 (Human-in-the-Loop CLI)
              │
              v
         Phase 6 (Evaluation & Polish)
```

**Parallel work:** Ground truth annotation starts Phase 2. Multimodal PDF extraction can start Phase 3.

---

## Total Effort

| Phase | Days | Cumulative |
|-------|------|------------|
| 0 — Data Layer | 5-7 | 5-7 |
| 1 — Service Hardening | 8-10 | 13-17 |
| 2 — Literature Mapping | 6-8 | 19-25 |
| 3 — Agent Completion | 7-9 | 26-34 |
| 4 — Multimodal + Proposal | 7-9 | 33-43 |
| 5 — CLI Interface | 5-7 | 38-50 |
| 6 — Evaluation & Polish | 6-8 | 44-58 |

**Total: 44-58 working days (~9-12 weeks)**

---

## Target Pipeline (Design.md 7-Step Flow)

```
1. Ingestion (PDF → chunks + embeddings → Chroma + SQLite)
2. Context Extraction (chunks → ExperimentalContext registry)
3a. Claim Extraction → Normalization → Contradiction → Belief  [linear]
3b. Literature Mapping (chunks → HDBSCAN → ClusterMap)         [parallel with 3a]
4. Hypothesis-Critique Loop (claims + contradictions + map → validated hypothesis)
5. Consolidation (hypothesis + beliefs + map → structured analysis)
6. Multimodal Extraction (PDF → tables, metrics)                [parallel, starts at step 1]
7. Proposal Generation (hypothesis + evidence + tables → Markdown/LaTeX)
```

---

## Critical Files (most-touched across phases)

1. `services/orchestrator/mcp_orchestrator.py` — DAG execution, pause/resume, full pipeline wiring
2. `services/rag/service.py` — Lexical → semantic upgrade; backbone for CAP 1, 2, 3
3. `agents/loop.py` — Convergence detection, confidence rationale, intervention points
4. `services/extraction/service.py` — Yield improvement; biggest quality bottleneck
5. `core/schemas/cluster_map.py` — CAP 1 output contract; zero implementation today
6. `core/llm/prompts.py` — All LLM prompts centralized with versioning
7. `services/orchestrator/workflows.py` — Workflow definitions evolve every phase

## Verification

After all phases:
1. Run `python -m cli.app ingest <5 test PDFs>` → chunks persisted
2. Run `python -m cli.app analyze <paper_id>` → full 7-step pipeline completes
3. Run `python -m cli.app trace <session_id>` → every step has provenance
4. Run `python -m evaluation.benchmark_runner` → all metrics above thresholds
5. Run `pytest tests/ --cov=core --cov=services --cov=agents` → all pass, coverage > 80%
