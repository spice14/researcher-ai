# ScholarOS: Implementation Plan

> Derived exclusively from `Design.md`, `capabilities.md`, and `README.md`.

---

## Guiding Constraints

- Orchestrator = planner/controller only; no heavy reasoning
- MCP tool services = stateless, independently testable, deterministic
- Multi-agent reasoning = only for hypothesis generation and critique
- All outputs = schema-validated with provenance
- All components = local-first, self-hostable

---

## Phase 0 — Foundation & Infrastructure

**Goal:** Establish the non-negotiable base layer everything else depends on.

### 0.1 Repository Structure

```
ScholarOS/
├── core/
│   ├── schemas/          # All shared data contracts
│   ├── mcp/              # MCP protocol interfaces
│   └── validators/       # Schema validation logic
├── services/
│   ├── ingestion/        # PDF parsing, chunking, embedding
│   ├── rag/              # Semantic retrieval
│   ├── context/          # Literature mapping & clustering
│   ├── extraction/       # Multimodal (tables, metrics)
│   ├── normalization/    # Claim normalization
│   ├── contradiction/    # Consensus/contradiction engine
│   ├── belief/           # Evidence belief aggregation
│   └── orchestrator/     # DAG execution controller
├── agents/
│   ├── hypothesis/       # Hypothesis Agent
│   └── critic/           # Critic Agent
├── infra/
│   ├── docker/
│   └── config/
└── tests/
```

### 0.2 Infrastructure Components

| Component     | Technology                  | Purpose                                 |
| ------------- | --------------------------- | --------------------------------------- |
| Vector store  | Chroma                      | Semantic retrieval over paper chunks    |
| Metadata DB   | SQLite                      | Papers, sessions, hypotheses, artifacts |
| Session state | Redis or in-process dict    | Active execution state                  |
| Trace store   | JSON / Langfuse             | Full execution provenance               |
| PDF parsing   | PyMuPDF or pdfplumber       | PDF ingestion                           |
| Embeddings    | Local sentence-transformers | Chunk vectorization                     |
| LLM calls     | Ollama / local model        | Summarization, hypothesis, critique     |

### 0.3 MCP Protocol Interface (Applied to Every Service)

Every service exposes exactly two endpoints:

```
GET  /manifest  →  declares capabilities, input/output schemas, version
POST /call      →  executes action, returns structured response + trace
```

Each `/call` response wraps output in an `ExecutionTrace`:

- `trace_id`
- `service_name`
- `input_snapshot`
- `output_snapshot`
- `prompt_version` (if LLM used)
- `model_name` (if LLM used)
- `token_usage` (if LLM used)
- `latency_ms`
- `error_state`
- `timestamp`

**Deliverables:** Docker compose file, base MCP interface class, `ExecutionTrace` schema, local environment `.env` template.

---

## Phase 1 — Core Schemas & Validators

**Goal:** Define all data contracts before any service is implemented. Nothing in Phase 2+ is allowed to deviate from these.

### 1.1 Schemas to Define

**Paper**

```
paper_id, title, authors, abstract, doi, arxiv_id,
pdf_path, ingestion_timestamp, chunk_ids[]
```

**Chunk**

```
chunk_id, paper_id, text, page_number, embedding_id,
chunk_type (sentence | paragraph | caption | table)
```

**Claim**

```
claim_id, paper_id, chunk_id, text, claim_type,
metric_refs[], condition_refs[], confidence, extraction_method
```

**NormalizedClaim**

```
normalized_claim_id, canonical_text, source_claim_ids[],
domain, metric, conditions{}, evidence_strength
```

**ClusterMap** (Literature Mapping output)

```
map_id, seed_paper_id, clusters[{
  cluster_id, label, representative_paper_ids[],
  boundary_paper_ids[], centroid_embedding
}], provenance[]
```

**ContradictionReport**

```
report_id, claim_cluster_id, consensus_claims[],
contradiction_pairs[{claim_a, claim_b, evidence_a[], evidence_b[]}],
uncertainty_markers[]
```

**Hypothesis**

```
hypothesis_id, statement, rationale, assumptions[],
supporting_citations[], known_risks[], confidence_score,
grounding_claim_ids[], iteration_number
```

**Critique**

```
critique_id, hypothesis_id, counter_evidence[],
weak_assumptions[], suggested_revisions[], severity
```

**Proposal**

```
proposal_id, hypothesis_id, novelty_statement, motivation,
methodology_outline, expected_outcomes, references[]
```

**ExtractionResult** (Multimodal)

```
result_id, paper_id, page_number, artifact_type (table | figure | metric),
raw_content, normalized_data{}, caption, provenance
```

**Session**

```
session_id, user_input, active_paper_ids[], hypothesis_ids[],
phase, created_at, updated_at
```

### 1.2 Validators for Each Schema

Each schema gets a corresponding validator that:

- Checks required fields are present
- Validates field types and value ranges
- Rejects outputs missing provenance on assertion fields
- Raises structured errors (never silent failures)

**Deliverables:** All schema classes, all validators, schema unit tests with fixture inputs, failure-mode tests for each validator.

---

## Phase 2 — Deterministic Services (MCP Tool Layer)

Implemented in strict order. Each service is independently testable and exposes `/manifest` + `/call`.

### 2.1 Ingestion Service

**Purpose:** Convert raw PDFs into indexed, retrievable chunks.

**Steps:**

1. Accept PDF file path or URL
2. Parse PDF → extract raw text per page using PyMuPDF
3. Sentence-tokenize text → produce `Chunk` records
4. Separately extract captions and table regions → typed chunks
5. Generate embeddings for each chunk (batch, local model)
6. Store chunks in Chroma (vector DB)
7. Store paper + chunk metadata in SQLite
8. Return `Paper` schema with `chunk_ids[]`

**Failure modes to handle:**

- Corrupt or password-protected PDF → log error, return structured failure
- Embedding model unavailable → fail hard, no silent fallback
- Duplicate paper (same DOI/arxiv_id) → return existing paper_id, skip re-indexing

**Tests:** Parse valid PDF, parse corrupt PDF, duplicate detection, chunk count determinism across runs.

---

### 2.2 RAG Service

**Purpose:** Semantic retrieval over indexed content.

**Steps:**

1. Accept a query string + optional paper_id filter + top_k parameter
2. Embed query using same local model as ingestion
3. Query Chroma for nearest neighbors
4. Return ranked list of `Chunk` records with similarity scores and paper provenance
5. All results include `chunk_id`, `paper_id`, `score`, `text`

**Failure modes:** Empty index → return empty list with log warning, not an error.

**Tests:** Retrieval against known indexed content, score ordering, paper_id filtering, empty index behavior.

---

### 2.3 Contextual Mapping Service

**Purpose:** Build a semantic, clustered literature map from a seed paper or topic.

**Steps:**

1. Accept seed `paper_id` or topic string
2. Use RAG Service to retrieve top-N related papers
3. Collect chunk embeddings for each related paper → aggregate to paper-level embedding (mean pool)
4. Run HDBSCAN clustering on paper embeddings
5. For each cluster: identify representative papers (nearest to centroid), boundary papers (furthest within cluster)
6. Label each cluster: retrieve top chunks per cluster → constrained LLM call → structured label string (no free-form prose)
7. Assemble `ClusterMap` schema
8. Log LLM call with prompt version, model, token usage, trace_id

**Constraints:**

- LLM call is for labeling only — no reasoning
- Clustering is deterministic (fixed random seed)
- Minimum cluster size configurable
- Returns structured `ClusterMap`, not text

**Tests:** Deterministic cluster output for same input, single-paper edge case, LLM label format validation against schema.

---

### 2.4 Claim Extraction Service

**Purpose:** Extract structured claims from text chunks.

**Steps:**

1. Accept `paper_id` + `chunk_ids[]` (or all chunks for a paper)
2. For each chunk, apply rule-based extraction first:
   - Named metric patterns (accuracy, F1, BLEU, MAE, etc.)
   - Comparative language patterns ("outperforms," "achieves," "reduces")
   - Numeric result patterns
3. LLM-assisted extraction only for chunks that pass rule-based filters (reduces hallucination surface)
4. Each LLM call must return structured `Claim` — reject free-form
5. Validate each `Claim` against schema before storing
6. Return `claim_ids[]` with extraction metadata

**Failure modes:** LLM returns invalid schema → log, discard, do not substitute with prose.

**Tests:** Rule-based extraction on synthetic sentences, LLM extraction schema validation, rejection of claims missing metric refs.

---

### 2.5 Normalization Service

**Purpose:** Group semantically equivalent claims across papers into `NormalizedClaim` clusters.

**Steps:**

1. Accept `claim_ids[]`
2. Embed each claim text
3. Cluster claim embeddings (cosine similarity threshold)
4. For each cluster, select canonical text (highest confidence or most cited)
5. Produce `NormalizedClaim` records linking source claims
6. Return `normalized_claim_ids[]`

**Tests:** Two identical claims from different papers collapse to one normalized claim, dissimilar claims remain separate.

---

### 2.6 Contradiction & Consensus Service

**Purpose:** Identify where normalized claims agree, conflict, or are inconclusive.

**Steps:**

1. Accept `normalized_claim_ids[]`
2. Group claims by domain + metric (deterministic grouping)
3. For each group, compare condition sets (controlled by `ExperimentalContext` identity — not overlap)
4. Flag contradictions: same metric, same context, conflicting quantitative results
5. Flag consensus: same metric, same context, converging results (within tolerance)
6. Flag uncertainty: insufficient evidence
7. Produce `ContradictionReport` schema
8. Associate each contradiction/consensus entry with specific `chunk_ids[]` as evidence

**Constraints:** No LLM for this step — purely deterministic comparison logic.

**Tests:** Two contradicting claims are correctly flagged, two agreeing claims produce consensus, same-claim-different-context is not a contradiction.

---

### 2.7 Multimodal Extraction Service

**Purpose:** Extract tables, figures, and numeric metrics from PDFs as structured data.

**Steps:**

1. Accept `paper_id` + optional page constraint
2. Use pdfplumber (or equivalent) for table extraction → parse cell data
3. Use PDF layout analysis to identify figure regions + captions
4. Normalize extracted table data → typed rows/columns
5. Associate tables/metrics with claims from same paper where possible
6. Return `ExtractionResult[]` with `paper_id`, `page_number`, `artifact_type`, `normalized_data`, `caption`, provenance

**Failure modes:** Table parse failure → log and return partial results with error_state, never discard silently.

**Tests:** Table extraction from synthetic PDF, caption association, missing caption handling.

---

### 2.8 Proposal/Artifact Service

**Purpose:** Convert a validated hypothesis + evidence into a structured research artifact.

**Steps:**

1. Accept `hypothesis_id` + `supporting_claim_ids[]` + optional constraints (funding agency, word limit)
2. Retrieve hypothesis + critiques + evidence from store
3. Structure sections: novelty statement, motivation, methodology outline, expected outcomes
4. LLM call per section with constrained prompt → validate output length and structure
5. Assemble `Proposal` schema
6. Generate formatted output (Markdown, with LaTeX option)
7. Attach fully cited reference list from `paper_ids[]` in evidence chain

**Constraints:** LLM generates section text only; structure and citations are deterministic.

**Tests:** Proposal schema validation, reference list completeness check, empty hypothesis rejection.

---

## Phase 3 — Agent Reasoning Layer

Agents operate only on structured schemas. No free-form reasoning outputs.

### 3.1 Hypothesis Agent

**Purpose:** Propose testable, literature-grounded hypotheses.

**Inputs (structured):**

- `ClusterMap` (from Contextual Mapping)
- `ContradictionReport` (identifies gaps and conflicts)
- Optional: user constraints (scope, domain, feasibility)

**Algorithm:**

1. Identify candidate gaps: contradiction pairs with no consensus + high-evidence contradiction
2. For each gap, construct a structured hypothesis prompt including:
   - Contradiction summary (structured, not prose)
   - Relevant normalized claims (with IDs)
   - Explicit assumption list (injected deterministically)
   - Prompt version string
3. Call LLM → parse response into `Hypothesis` schema
4. Validate schema — reject if `confidence_score` absent or `grounding_claim_ids` empty
5. Store hypothesis with `iteration_number=1`
6. Return `hypothesis_id`

**Loop bounds:** Maximum iterations configurable (default: 5). Stop when confidence threshold met or max reached.

**Logging:** Every iteration logs `prompt_version`, `model_name`, `token_usage`, `latency_ms`, `trace_id`.

**Tests:** Hypothesis schema compliance, `grounding_claim_ids` non-empty, iteration counter increments correctly, loop bound enforced.

---

### 3.2 Critic Agent

**Purpose:** Challenge hypotheses using counter-evidence.

**Inputs (structured):**

- `hypothesis_id`
- Access to RAG Service (counter-evidence retrieval)
- `ContradictionReport`

**Algorithm:**

1. Retrieve hypothesis assumptions and supporting claims
2. For each assumption: query RAG for counter-evidence
3. For each supporting claim: search `ContradictionReport` for contradictions
4. Construct adversarial prompt with:
   - Hypothesis statement
   - Specific assumptions to challenge
   - Counter-evidence chunks (with IDs)
   - Prompt version string
5. Call LLM → parse response into `Critique` schema
6. Validate: `counter_evidence[]` must reference real `chunk_ids[]`
7. Store `Critique` linked to `hypothesis_id`
8. Return `critique_id`

**Loop bounds:** Same configurable maximum as Hypothesis Agent.

**Tests:** Critique references valid `chunk_ids`, severity field validation, empty counter-evidence case handled.

---

### 3.3 Hypothesis-Critique Iteration Loop

The Orchestrator manages the loop:

1. Hypothesis Agent proposes → Critic Agent challenges
2. Hypothesis Agent revises (increments `iteration_number`) using critique
3. Repeat until: `confidence_score` ≥ threshold OR `iteration_number` ≥ `max_iterations` OR user interrupt
4. Final hypothesis + full revision history returned as structured output

---

## Phase 4 — Orchestrator (DAG Executor)

**Purpose:** Coordinate execution of services and agents via pre-declared task graphs. Must remain deterministic and inspectable.

### 4.1 Task Graph

```
Ingest Papers
    ↓
Extract Chunks + Claims
    ↓
Normalize Claims
    ↓
Build Literature Map (Contextual Mapping)
    ↓                    ↓
Contradiction Engine    [Optional: Multimodal Extraction]
    ↓
Hypothesis Agent
    ↓
Critic Agent  ←──────────────┐
    ↓                        │
Revised Hypothesis ──────────┘  (loop until done)
    ↓
Proposal Generation (optional)
```

### 4.2 Orchestrator Responsibilities

- Accept user input (paper set + intent)
- Resolve task graph dependencies
- Execute each task by calling corresponding MCP service `/call`
- Pass outputs of one task as inputs to the next (context construction)
- Handle retries on transient failures (bounded: max 3 retries per task)
- Log every task execution as a trace entry
- Maintain `Session` record with current phase
- Return consolidated results with provenance

### 4.3 Orchestrator Constraints

- Must NOT embed large prompts — delegate to agents
- Must NOT perform reasoning — delegate to agents
- Must NOT contain domain logic — delegate to services
- All task graphs are pre-declared, not dynamically generated
- Failure handling is explicit: log error, mark task failed, surface to user

### 4.4 Context Pruning

- Session context is pruned per task based on declared input schema
- No unbounded context accumulation

**Tests:** Full DAG execution with mocked services, retry logic, failure isolation (one task failure does not corrupt session), trace completeness.

---

## Phase 5 — Observability & Evaluation

**Purpose:** Ensure every action is inspectable, reproducible, and auditable.

### 5.1 Structured Logging

Every service and agent emits:

```json
{
  "trace_id": "...",
  "service": "...",
  "action": "...",
  "input_hash": "...",
  "output_hash": "...",
  "latency_ms": 0,
  "model": "...",
  "prompt_version": "...",
  "token_usage": {},
  "error": null,
  "timestamp": "..."
}
```

### 5.2 Determinism Verification

- For every document in the corpus, hash outputs across two independent runs
- Non-determinism in deterministic services = bug, must be fixed before merge
- LLM outputs: compare schema structure (not content) for determinism

### 5.3 Evaluation Metrics

| Metric                    | What it measures                                            |
| ------------------------- | ----------------------------------------------------------- |
| Claim extraction yield    | Claims extracted / expected claims per paper                |
| Normalization precision   | Collapsed claims that are truly equivalent                  |
| Contradiction recall      | Contradictions found / known contradictions in ground truth |
| Hypothesis grounding rate | % of hypotheses with non-empty `grounding_claim_ids`        |
| Proposal completeness     | % of required sections present and non-empty                |

### 5.4 Provenance Audit

Any output asserting a claim, hypothesis, or conclusion must trace to:

- A specific `chunk_id` in a specific `paper_id`, **or**
- Be explicitly marked `confidence: LOW, ungrounded: true`

Outputs failing provenance audit are flagged, not silently passed.

---

## Implementation Sequence

> Do not begin Step N+1 until Step N has passing tests and schema validation.

| Step | Component                             | Dependency             |
| ---- | ------------------------------------- | ---------------------- |
| 1    | Core schemas + validators             | None                   |
| 2    | MCP base interface + `ExecutionTrace` | Schemas                |
| 3    | Ingestion Service                     | MCP interface          |
| 4    | RAG Service                           | Ingestion              |
| 5    | Claim Extraction Service              | RAG, Schemas           |
| 6    | Normalization Service                 | Extraction             |
| 7    | Contradiction & Consensus Engine      | Normalization          |
| 8    | Contextual Mapping Service            | RAG                    |
| 9    | Hypothesis Agent                      | Mapping, Contradiction |
| 10   | Critic Agent                          | Hypothesis, RAG        |
| 11   | Hypothesis-Critique Loop              | Both agents            |
| 12   | Multimodal Extraction Service         | Ingestion              |
| 13   | Proposal/Artifact Service             | Hypothesis, Critique   |
| 14   | Orchestrator (DAG)                    | All services + agents  |
| 15   | Observability + evaluation tooling    | Orchestrator           |

---

## Testing Requirements per Phase

| Phase        | Required Tests                                                          |
| ------------ | ----------------------------------------------------------------------- |
| Schemas      | Field presence, type validation, rejection of invalid inputs            |
| Each service | Unit tests, schema compliance, failure modes, determinism across 2 runs |
| Each agent   | Schema output compliance, loop bound enforcement, grounding non-empty   |
| Orchestrator | DAG execution, retry logic, task isolation, trace completeness          |
| End-to-end   | Full pipeline on 1 synthetic paper, provenance audit passes             |

---

## What is Explicitly Out of Scope

- Chat or conversational interface
- Cloud-only deployment
- Autonomous operation without user checkpoints
- Claim generation without evidence
- Statistical meta-analysis (contradiction engine compares, does not analyze)
- Experiment execution or code generation
