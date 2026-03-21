# ScholarOS — Technical Architecture Overview

This document describes the **technical design, system architecture, and execution model** of **ScholarOS**.

It is intended for engineers, researchers, and reviewers who want to understand **how the system works**, why specific architectural choices were made, and how the components interact to support rigorous, evidence-driven research workflows.

---

## System Objective

ScholarOS is designed to assist academic research by automating **high-latency cognitive and operational tasks** while preserving:

- traceability of evidence
- transparency of reasoning
- human control over judgment

The system explicitly avoids monolithic or opaque AI behavior and instead decomposes research assistance into **structured, inspectable components**.

---

## Architectural Principles

The system is built around the following non-negotiable principles:

### 1. Separation of Concerns

Retrieval, reasoning, extraction, and generation are implemented as **distinct components**, not collapsed into a single LLM call.

### 2. Selective Agentic Reasoning

Multi-agent (A2A) reasoning is used **only where adversarial or reflective reasoning adds value** (e.g., hypothesis critique). Deterministic tasks are implemented as services.

### 3. Protocol-First Design (MCP)

All components communicate via a uniform **Model Context Protocol (MCP)** interface, enabling loose coupling and extensibility.

### 4. Provenance-First Outputs

All outputs that assert claims, hypotheses, or conclusions must be traceable to source material or explicitly marked as uncertain.

### 5. Local-First Execution

The system supports local inference and self-hosted infrastructure to reduce cost, protect sensitive research data, and improve reproducibility.

---

## Deprecations (Epistemic Re-Anchor)

The following legacy assumptions are explicitly deprecated and must not be revived in new components:

- Claim condition overlap as a primary comparator (superseded by ExperimentalContext identity).
- Paragraph-level chunking as an epistemic unit (superseded by sentence-level atoms).

These deprecations are binding for all subsequent design and implementation work.

---

## High-Level System Architecture

ScholarOS uses a **hybrid architecture** consisting of:

- A central **Orchestrator** (planner/controller)
- A set of **deterministic MCP tool services**
- A small number of **specialized reasoning agents**
- Shared data stores for memory and traceability

The orchestrator coordinates execution but does not perform heavy reasoning itself.

---

## Core Components

### 1. Orchestrator (Planner / Controller)

The orchestrator is responsible for:

- Interpreting user intent
- Discovering available MCP services and agents
- Executing task graphs (sequential or conditional)
- Managing session state and context pruning
- Handling retries and failure recovery
- Logging all actions for traceability

The orchestrator delegates:

- computation → tools
- judgment → agents

This design prevents the orchestrator from becoming a brittle “god agent.”

---

### 2. MCP Tool Services (Deterministic Layer)

All tools are implemented as independent FastAPI services exposing:

- `GET /manifest` — declares capabilities and schemas
- `POST /call` — executes a specific action

Each tool is stateless where possible and independently testable.

#### a. Ingestion Service

- Parses PDFs and metadata
- Chunks text and generates embeddings
- Stores structured metadata in SQL
- Stores embeddings in a vector database

#### b. RAG Service

- Provides semantic retrieval over indexed content
- Returns ranked snippets with identifiers and scores
- Serves as the evidence backbone for all reasoning agents

#### c. Contextual Mapping Service

- Performs nearest-neighbor retrieval around a seed paper or topic
- Clusters papers using unsupervised methods (e.g., HDBSCAN)
- Labels clusters using constrained LLM summarization
- Produces a structured representation of the research landscape

#### d. Multimodal Extraction Service

- Extracts tables, metrics, and structured results from PDFs
- Preserves links to original captions and page locations
- Outputs normalized, machine-readable data

#### e. Proposal / Artifact Service

- Converts validated hypotheses into structured research documents
- Produces editable outputs (Markdown, LaTeX)
- Automatically assembles citations and references

---

### 3. Selective Multi-Agent Reasoning Layer

Multi-agent interaction is introduced **only for tasks involving epistemic uncertainty or debate**.

#### Hypothesis Agent

- Proposes testable, literature-grounded hypotheses
- Explicitly states assumptions and rationale
- Produces structured outputs with confidence estimates

#### Critic Agent

- Challenges hypotheses using counter-evidence
- Identifies missing controls or weak assumptions
- Returns structured critiques with citations

The orchestrator may run these agents in iterative loops until:

- confidence thresholds are met
- a maximum iteration count is reached
- the user intervenes

This mirrors real research dynamics: proposal followed by critique.

---

## Data and Memory Model

ScholarOS maintains multiple explicit memory layers:

- **Vector memory** (Chroma): semantic representations of text chunks
- **Structured metadata** (SQLite): papers, sessions, hypotheses, artifacts
- **Session memory** (Redis or in-process): active execution state
- **Trace memory** (JSON / Langfuse): full execution provenance

No long-term state is hidden inside the LLM.

---

## Execution Flow (Typical Session)

1. User submits a paper or topic
2. Orchestrator triggers ingestion and indexing
3. Contextual mapping builds a semantic view of related literature
4. Hypothesis Agent proposes candidate hypotheses
5. Critic Agent evaluates and challenges them
6. Orchestrator consolidates validated hypotheses and evidence
7. Optional extraction and proposal generation steps are executed
8. Results are returned with provenance and confidence annotations

At any step, the user may inspect, intervene, or redirect execution.

---

## Observability and Traceability

Every system action generates a trace entry containing:

- input arguments
- prompts and model calls
- outputs and intermediate results
- evidence snippets used
- confidence estimates
- timestamps and execution metadata

This enables:

- debugging incorrect reasoning
- auditing hallucinations
- reproducing results
- human review before downstream use

Observability is treated as a **first-class system concern**.

---

## Error Handling and Safety

- All LLM outputs are schema-validated
- Outputs without provenance are flagged as low confidence
- Tool failures are isolated and do not corrupt session state
- Agent loops are bounded by iteration and token limits
- The system fails explicitly rather than silently hallucinating

---

## What This Architecture Avoids

ScholarOS explicitly avoids:

- Monolithic “do everything” agents
- Hidden long-term memory inside LLMs
- Autonomous decision-making without review
- Claim generation without evidence
- Domain-specific hardcoding

---

## Extensibility

New capabilities can be added by:

- implementing a new MCP-compliant service or agent
- registering it via a manifest
- updating orchestrator task graphs

No refactoring of existing components is required.

---

## Summary

ScholarOS is a modular, agentic research system that treats academic work as a structured, evidence-driven process.

By combining MCP-based tooling, selective multi-agent reasoning, and provenance-first outputs, the system provides meaningful research assistance without obscuring uncertainty or replacing human judgment.

It is designed to think **with** researchers, not **instead of** them.
