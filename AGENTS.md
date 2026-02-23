# AGENTS.md — Implementation Rules for AI Coding Assistants

This file defines **strict behavioral and architectural constraints** for AI coding agents
(e.g., GitHub Copilot, ChatGPT, Claude, etc.) contributing to **Researcher-AI**.

The goal is to ensure that automated code generation:

- Preserves system architecture
- Enforces schema discipline
- Avoids hidden reasoning behavior
- Produces production-grade, testable components
- Accelerates completion without degrading rigor

This document is **normative**.  
AI-generated code must comply.

---

# 1. Core Mandate

AI agents must prioritize:

**Correct architecture > speed of code generation > verbosity > creativity**

If a generated solution violates architecture, it must be rejected even if it is faster or simpler.

---

# 2. Absolute Prohibitions

AI agents MUST NOT:

- Introduce hidden global state
- Store reasoning inside prompts or comments instead of structured data
- Collapse multi-step pipelines into a single LLM call
- Bypass schemas using free-form text
- Add silent retries, fallbacks, or heuristics without logging
- Introduce new dependencies without clear necessity
- Modify core schemas without explicit human approval
- Implement autonomous agent loops without iteration bounds
- Generate claims or confidence values without provenance logic

Violations require rewrite, not patching.

---

# 3. Repository Mental Model

AI agents must understand the system as **four strict layers**:

## 3.1 Deterministic Services Layer (`/services`)

Contains:

- ingestion
- RAG retrieval
- clustering / mapping
- multimodal extraction
- proposal drafting utilities

Rules:

- Prefer deterministic algorithms over LLM calls
- Every endpoint must be independently testable
- Must expose MCP-compatible interfaces
- Must validate inputs/outputs against schemas

---

## 3.2 Agent Reasoning Layer (`/agents`)

Contains:

- hypothesis agent
- critic agent

Rules:

- Agents operate ONLY on structured schemas
- No free-form reasoning outputs
- Every statement must trace to evidence or assumptions
- Iteration loops MUST be bounded and configurable
- Prompts must be versioned and logged

Agents are **not orchestration engines**.

---

## 3.3 Orchestrator Layer (`/orchestrator`)

Responsible for:

- DAG execution
- dependency resolution
- context construction
- retry logic
- trace logging

Rules:

- Must remain deterministic and inspectable
- Must NOT contain heavy reasoning
- Must NOT embed large prompts
- Must execute pre-declared task graphs only

If orchestrator becomes “smart,” architecture is broken.

---

## 3.4 Infrastructure Layer (`/infra`)

Contains:

- Docker
- environment config
- service wiring
- observability setup

Rules:

- Must support **local-first execution**
- Must not assume cloud services
- Must expose reproducible dev environment

---

# 4. Schema Discipline (Non-Negotiable)

AI agents MUST:

- Use existing JSON schemas exactly
- Validate all outputs before returning
- Refuse generation if schema cannot be satisfied
- Never replace structured fields with prose

If schema friction occurs → **fix the implementation, not the schema**.

---

# 5. LLM Usage Rules

LLMs may be used ONLY for:

- summarization with evidence references
- hypothesis generation from structured inputs
- adversarial critique
- constrained labeling or normalization

LLMs MUST NOT be used for:

- raw retrieval
- numeric extraction
- orchestration decisions
- confidence scoring without calibration logic
- silent background reasoning

All LLM calls must include:

- prompt version
- model name
- token usage
- latency
- trace ID

---

# 6. Implementation Order (Critical for Completion Speed)

AI agents must generate code in this **strict sequence**:

1. **Core schemas & validators**
2. **Deterministic ingestion + RAG retrieval**
3. **Claim extraction → Claim schema compliance**
4. **Contradiction / consensus engine**
5. **Hypothesis agent**
6. **Critic agent**
7. **DAG orchestrator**
8. **Multimodal extraction**
9. **Proposal generation**
10. **Observability + evaluation tooling**

Do NOT jump ahead to UI, chat interfaces, or demos.

Architecture before appearance.

---

# 7. Testing Requirements

Every generated component MUST include:

- Unit tests
- Schema validation tests
- Failure-mode tests
- Deterministic reproducibility checks

LLM components additionally require:

- prompt snapshot tests
- structured output validation
- regression fixtures

Untested code is considered incomplete.

---

# 8. Observability Enforcement

All generated code must emit:

- structured logs
- trace IDs
- timing metrics
- error states
- model metadata (if LLM used)

Silent failure is unacceptable.

---

# 9. Performance Constraints

AI agents must prefer:

- streaming over blocking where meaningful
- batching for embeddings/retrieval
- lazy loading of heavy models
- CPU fallbacks for local execution

Never assume high-end GPU availability.

---

# 10. Documentation Requirements

Any non-trivial generated module MUST include:

- purpose
- inputs/outputs
- schema references
- failure modes
- testing strategy

No decorative comments.  
Only operational clarity.

---

# 11. When AI Agents Must Stop and Ask for Human Input

Agents MUST halt and request guidance if:

- schema changes are required
- architectural boundaries are unclear
- conflicting design goals appear
- scientific interpretation is required
- evaluation metrics are undefined

Silent guessing is forbidden.

---

# 12. Definition of “Done”

A feature is complete ONLY when:

- Code compiles
- Tests pass
- Schemas validate
- Logs emit correctly
- Traces are reproducible
- No architectural violations exist

Demo output alone does NOT count.

---

# Final Directive

AI agents contributing to Researcher-AI must behave like:

**careful systems engineers working on scientific infrastructure**  
—not like chatbot demo generators.

Speed matters.  
But **epistemic integrity matters more**.
