"""Phase 5 audit runner.

Usage:
    python scripts/phase5_audit_report.py \
        --input outputs/phase5_input.json \
        --output outputs/phase5_report.json

Input JSON contract:
{
  "document_runs": {
    "paper_a": [{"final": "..."}, {"final": "..."}],
    "paper_b": [{"final": "..."}, {"final": "..."}]
  },
  "evaluation_rows": [
    {
      "paper_id": "paper_a",
      "expected_claims": 10,
      "extracted_claims": 8,
      "collapsed_claim_pairs": 4,
      "truly_equivalent_collapses": 3,
      "known_contradictions": 5,
      "contradictions_found": 3,
      "hypotheses_generated": 2,
      "hypotheses_grounded": 1,
      "proposals_generated": 1,
      "proposals_complete": 1
    }
  ],
  "assertions": [
    {"assertion_id": "a1", "paper_id": "p", "chunk_id": "c"}
  ]
}
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure workspace root is on path when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.observability.phase5 import (
    EvaluationInput,
    audit_provenance_assertions,
    compute_evaluation_metrics,
    verify_determinism_by_document,
)


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5 audit checks")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", required=True, help="Path to output JSON report")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = _load_json(input_path)

    document_runs = payload.get("document_runs", {})
    evaluation_rows = [EvaluationInput(**row) for row in payload.get("evaluation_rows", [])]
    assertions = payload.get("assertions", [])

    determinism = verify_determinism_by_document(document_runs)
    metrics = compute_evaluation_metrics(evaluation_rows)
    provenance = audit_provenance_assertions(assertions)

    report = {
        "determinism": determinism.model_dump(),
        "evaluation": metrics.model_dump(),
        "provenance": provenance.model_dump(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Phase 5 report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
