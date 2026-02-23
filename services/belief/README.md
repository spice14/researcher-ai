# Belief Engine

## Purpose

Deterministic belief state computation from normalized claims and contradiction results.

Converts structured claim data into epistemic belief states with:
- Explicit confidence thresholds
- Deterministic status classification
- Full provenance tracing

## Architecture

**No LLM usage.**  
**No embeddings.**  
**No probabilistic scoring.**  
**No hidden heuristics.**

All logic is rule-based with explicit constants.

## Confidence Calibration

### HIGH Confidence

```
supporting_count >= 3
AND support_ratio >= 0.75
AND contradiction_density <= 0.2
```

### MEDIUM Confidence

```
supporting_count >= 2
AND support_ratio >= 0.6
```

### LOW Confidence

All other cases.

## Epistemic Status Classification

| Status | Rule |
|--------|------|
| `insufficient_evidence` | No claims in group |
| `supported` | support_ratio >= 0.75 AND refuting_count == 0 |
| `contested` | refuting_count > supporting_count |
| `weakly_supported` | support_ratio between 0.4 and 0.75 |

## Integration

### Input Contract

```python
BeliefRequest {
    normalized_claims: List[NormalizedClaim]
    contradiction_records: List[ContradictionRecord]  # Optional
}
```

### Output

```python
List[BeliefState]
```

One `BeliefState` per unique `(context_id, metric)` pair.

## Determinism Guarantee

Identical input → identical output.

All BeliefState fields are:
- Computed from structured data only
- Serializable to JSON
- Reproducible across runs

## Testing

See `tests/services/test_belief_engine.py` for:
- Confidence calibration tests
- Epistemic status classification tests
- Edge-case coverage (no claims, only support, only refute, equal split)
- Determinism validation
- Epistemic invariants (adding refutations never increases confidence)
