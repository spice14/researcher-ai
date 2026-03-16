# Agents Layer

This directory contains structured reasoning agents.

Planned modules:
- hypothesis: propose literature-grounded hypotheses from structured inputs
- critic: challenge hypotheses with counter-evidence
- loop orchestration: bounded hypothesis-critique iteration

Constraints:
- Structured inputs/outputs only
- Schema validation on all outputs
- Bounded iteration loops
- Prompt versioning and trace logging for every LLM call
