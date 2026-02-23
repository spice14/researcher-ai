# Deterministic Normalization (Step 3B)

Purpose: Canonicalize numeric values, units, and metric names for claims.

Inputs:
- `NormalizationRequest` with a `Claim`

Outputs:
- `NormalizedClaim` on success
- `NoNormalization` with reason code otherwise

Rules:
- Metric canonicalization uses a bounded alias map.
- Unit normalization is deterministic and limited to known units.
- No semantic inference beyond canonicalization.

Failure Modes:
- `missing_metric`
- `missing_value`
- `unparseable_unit`

Testing:
- Deterministic output checks
- Unit conversion verification
- Metric alias coverage
