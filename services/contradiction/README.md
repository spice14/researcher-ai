# Deterministic Contradiction + Consensus (Step 4)

Purpose: Compare normalized claims within identical ExperimentalContext identity and emit contradictions or consensus groups.

Inputs:
- `AnalysisRequest` with `NormalizedClaim` list

Outputs:
- `contradictions` list
- `conditional_divergences` for context mismatches
- `consensus` groups with contradiction density

Rules:
- Claims are comparable only if `context_id`, subject, predicate, and metric match.
- Polarity opposition yields a contradiction.
- Value divergence beyond tolerance yields a contradiction.
- Context mismatch yields conditional divergence.

Failure Modes:
- Unsupported unit falls back to default tolerance.

Testing:
- Polarity opposition
- Value divergence
- Consensus grouping
- Context mismatch
- Metric mismatch
