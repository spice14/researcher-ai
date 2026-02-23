# Deterministic Claim Extraction (Phase 3A)

Purpose: Convert sentence-level chunks into structured Claim objects without LLMs.

Inputs:
- `ClaimExtractionRequest` with an `IngestionChunk`

Outputs:
- `Claim` on success
- `NoClaim` with reason code otherwise

Rules:
- Requires deterministic sentence chunking upstream
- Requires `context_id` not equal to `ctx_unknown`
- Requires numeric strings and metric names
- Rejects hedged statements (e.g., "may", "reportedly")
- Rejects non-performance numeric usage (e.g., dataset splits, epochs)
- Rejects compound metric sentences (atomicity enforcement)
- Uses a bounded verb lexicon for predicate selection

Failure Modes:
- `context_missing`
- `hedged_statement`
- `no_number`
- `no_metric`
- `no_predicate`
- `non_performance_numeric`
- `compound_metric`
- `subject_missing`
- `object_missing`

Testing:
- Determinism tests
- True-positive / true-negative gate
- Context integrity
