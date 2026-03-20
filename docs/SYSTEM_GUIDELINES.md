# ScholarOS — System Design & Component Governance

This document defines the **formal engineering constraints, schemas, execution rules, and validation standards** governing ScholarOS.

It exists to prevent architectural drift, eliminate hidden reasoning behavior, and ensure that all outputs remain:

- Evidence-bound
- Inspectable
- Reproducible
- Scientifically defensible

This document is normative. All components must conform.

---

# 1. Global System Invariants

## 1.1 No Hidden State

- No persistent LLM memory.
- No unlogged reasoning chains.
- All intermediate artifacts must be serializable.
- All LLM outputs must be schema-validated.

If a component cannot produce structured, validated output, it is not considered production-ready.

---

## 1.2 Typed Intermediate Representations

All internal reasoning must operate over structured schemas.

Unstructured text is permitted only:

- At ingestion boundaries
- At final artifact generation boundaries

All intermediate system representations must be explicit JSON objects.

---

## 1.3 Evidence-Bound Assertions

Any claim, hypothesis, or conclusion must include explicit provenance:

- `source_id`
- `location` (page, section, or paragraph)
- `evidence_snippet`
- `retrieval_score`

Outputs missing provenance must be labeled:

```json
{
  "status": "UNVERIFIED"
}
```

---

## 1.4 Deterministic Before Agentic

If a task can be implemented deterministically, it must not rely on an LLM.

LLMs are reserved for:

- Abstraction
- Synthesis
- Interpretation under uncertainty
- Adversarial critique

---

# 1.5 Layer-0 Epistemic Foundations

This section defines the non-negotiable epistemic substrate used by all downstream components.

## 1.5.1 Sentence as Epistemic Atom

- All downstream reasoning operates on sentence-level units.
- Paragraph-level semantics are non-authoritative.
- Chunking must align with sentence boundaries before any claim extraction.

## 1.5.2 ExperimentalContext as Identity Carrier

- Claims are comparable only within identical experimental contexts.
- ExperimentalContext is the primary identity carrier.
- Legacy condition overlap logic is deprecated as a comparator.

## 1.5.3 Deterministic Preprocessing Contract

All inputs must pass through the deterministic pipeline in order:

1. Segmentation (sentence boundaries)
2. Context extraction (ExperimentalContext identity)
3. Normalization (units, metrics, variable names)
4. Reasoning (claims, contradictions, hypotheses)

No reasoning is permitted before normalization.

---

# 2. Core Epistemic Schemas

These schemas define the structured backbone of ScholarOS and are mandatory.

---

## 2.1 Claim Schema

```json
{
  "claim_id": "string",
  "context_id": "string | null",
  "subject": "string",
  "predicate": "string",
  "object": "string",
  "conditions": {
    "dataset": "string | null",
    "sample_size": "integer | null",
    "domain": "string | null",
    "experimental_setting": "string | null",
    "constraints": ["string"]
  },
  "evidence": [
    {
      "source_id": "string",
      "page": "integer",
      "snippet": "string",
      "retrieval_score": "float"
    }
  ],
  "polarity": "supports | refutes | neutral",
  "confidence_level": "low | medium | high"
}
```

**Constraints**

- Claims must be atomic.
- Compound claims must be decomposed.
- ExperimentalContext identity is required for comparability.
- Conditions are legacy metadata only and must not be used for identity or contradiction logic.

---

## 2.2 Hypothesis Schema

```json
{
  "hypothesis_id": "string",
  "statement": "string",
  "assumptions": ["string"],
  "independent_variables": ["string"],
  "dependent_variables": ["string"],
  "boundary_conditions": ["string"],
  "supporting_claims": ["Claim"],
  "contradicting_claims": ["Claim"],
  "novelty_basis": "string",
  "revision_history": [
    {
      "iteration": "integer",
      "changes": "string",
      "rationale": "string"
    }
  ],
  "qualitative_confidence": "low | medium | high"
}
```

**Constraints**

- No hypothesis without assumptions.
- Boundary conditions are mandatory when applicable.
- Revision history must persist across critique cycles.

---

## 2.3 Evidence Record Schema

```json
{
  "evidence_id": "string",
  "source_id": "string",
  "type": "text | table | figure",
  "extracted_data": {},
  "context": {
    "caption": "string | null",
    "method_reference": "string | null",
    "metric_name": "string | null",
    "units": "string | null"
  },
  "provenance": {
    "page": "integer",
    "bounding_box": "object | null",
    "extraction_model_version": "string"
  }
}
```

All extracted numeric values must preserve unit information where available.

---

# 3. Orchestrator Governance

The orchestrator must remain predictable and inspectable.

## 3.1 Execution Model

All workflows must be represented as **Directed Acyclic Graphs (DAGs)**.

```json
{
  "task_id": "string",
  "component": "string",
  "input_schema": "string",
  "output_schema": "string",
  "retry_policy": {
    "max_retries": "integer",
    "backoff_strategy": "string"
  },
  "timeout_seconds": "integer",
  "dependencies": ["task_id"]
}
```

Unbounded dynamic planning is not permitted.

---

## 3.2 Intent Classification

User input must resolve to one of:

- `literature_mapping`
- `contradiction_analysis`
- `hypothesis_generation`
- `multimodal_extraction`
- `proposal_generation`

Free-form “general research” execution paths are disallowed.

---

## 3.3 Context Budget Management

LLM context must be constructed through:

- Ranked retrieval
- Relevance filtering
- Explicit token budgeting

Entire session histories must never be blindly forwarded to models.

---

# 4. Contradiction & Consensus Rules

## 4.1 Claim Normalization

Before comparison:

- Standardize units.
- Normalize variable names.
- Extract ExperimentalContext identity.
- Record conditions as descriptive metadata only.
- Remove hedging language where appropriate.

Without normalization, semantic comparison is invalid.

---

## 4.2 Contradiction Criteria

A contradiction requires:

- Identical subject and predicate
- Identical ExperimentalContext identity
- Opposing polarity

Contradiction detection must operate solely on ExperimentalContext identity.
Conditions must not be used for overlap inference.

If ExperimentalContext differs, mark as:

```
conditional_divergence
```

---

## 4.3 Consensus Strength Estimation

Consensus must be computed using explicit rules based on:

- Number of independent supporting sources
- Methodological similarity
- Recency weighting
- Contradiction density

All heuristic scoring functions must be documented in code.

---

# 5. Hypothesis & Critique Loop Constraints

## 5.1 Iteration Boundaries

- Default `max_iterations = 3`
- Configurable upper bound required
- Hard token cap per iteration

Unbounded loops are prohibited.

---

## 5.2 Critique Dimensions

Critiques must explicitly label:

- `logical_coherence`
- `novelty`
- `empirical_support`
- `feasibility`
- `methodological_weakness`
- `missing_controls`

Each critique item must cite evidence where applicable.

---

## 5.3 Convergence Conditions

The loop must terminate when:

- No new contradicting claims are found
- Confidence stabilizes
- Iteration cap reached
- User intervention

---

# 6. Multimodal Extraction Validation

## 6.1 Structural Validation

Extracted tables must pass:

- Row/column consistency checks
- Numeric parsing validation
- Unit normalization
- Missing value detection

Failure must trigger:

```
extraction_confidence: "low"
```

---

## 6.2 Metric Attribution

Every extracted metric must link to:

- Dataset
- Evaluation method
- Model or approach
- Statistical significance (if available)

Incomplete metadata must be explicitly labeled.

---

# 7. Confidence Calibration Framework

Numeric probability outputs are **prohibited unless calibrated**.

System confidence must be **qualitative**, derived from:

- Evidence count
- Source diversity
- Contradiction density
- Retrieval score aggregation

Threshold rules must be explicitly documented.

---

# 8. Observability Requirements

Every execution must log:

- `task_id`
- Input hash
- Output hash
- Model version
- Prompt hash
- Token usage
- Latency
- Failure events

Observability is mandatory for reproducibility.

---

# 9. Local Execution Profiles

**Minimum**

- 16 GB RAM
- SSD storage
- CPU-based embedding fallback

**Recommended**

- 32 GB RAM
- Dedicated GPU (≥ 8 GB VRAM)

Degraded modes must declare capability limitations.

---

# 10. Evaluation Standards

Each core capability must have measurable benchmarks.

**Examples**

- Literature Mapping → cluster coherence, human agreement
- Contradiction Detection → precision/recall on annotated data
- Hypothesis Quality → blind expert scoring
- Multimodal Extraction → numeric accuracy vs ground truth

Claims of rigor must be supported by metrics.

---

# 11. Explicit Non-Goals

ScholarOS does **not**:

- Replace researchers
- Resolve scientific disagreement autonomously
- Perform statistical meta-analysis
- Conduct experiments
- Guarantee funding success

Human judgment remains authoritative.

---

# Conclusion

ScholarOS is designed as a **structured, modular research operating system**.

Its integrity depends on:

- Strict schema enforcement
- Bounded agentic reasoning
- Provenance-first outputs
- Transparent execution traces

Any component violating these principles must be revised before integration.
