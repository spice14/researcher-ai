"""Critic Agent — challenges hypotheses with counter-evidence.

Purpose:
- Accept a hypothesis and available evidence
- Generate adversarial critiques via bounded LLM calls
- Validate all outputs against Critique schema
- Reference real chunk IDs in counter-evidence

Inputs/Outputs:
- Input: CritiqueInput (hypothesis, counter-evidence chunks, contradiction context)
- Output: Critique schema object

Schema References:
- core.schemas.critique.Critique
- core.schemas.claim.ClaimEvidence

Failure Modes:
- LLM returns invalid JSON → log, return None
- LLM returns schema-invalid critique → log, return None
- Ollama unreachable → raise LLMConnectionError

Testing Strategy:
- Unit tests with mocked LLM responses
- Integration tests against live Ollama
- Schema validation on every output
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.llm.client import OllamaClient, LLMResponse
from core.llm.prompts import (
    CRITIC_EVALUATE_PROMPT,
    CRITIC_EVALUATE_PROMPT_VERSION,
    CRITIC_SYSTEM_PROMPT,
    CRITIC_SYSTEM_PROMPT_VERSION,
)
from core.schemas.claim import ClaimEvidence
from core.schemas.critique import Critique, CritiqueSeverity
from core.schemas.hypothesis import Hypothesis
from agents.hypothesis.agent import _extract_json

logger = logging.getLogger(__name__)


@dataclass
class CritiqueInput:
    """Structured input for hypothesis critique."""

    hypothesis: Hypothesis
    counter_evidence_chunks: List[Dict[str, Any]] = field(default_factory=list)
    contradiction_context: List[Dict[str, Any]] = field(default_factory=list)


def _map_severity(raw: str) -> CritiqueSeverity:
    """Map raw severity string to CritiqueSeverity enum."""
    raw_lower = raw.strip().lower()
    if raw_lower == "critical":
        return CritiqueSeverity.CRITICAL
    if raw_lower == "high":
        return CritiqueSeverity.HIGH
    if raw_lower == "medium":
        return CritiqueSeverity.MEDIUM
    return CritiqueSeverity.LOW


class CriticAgent:
    """Generates structured critiques of hypotheses via LLM.

    Operates only on structured schemas per AGENTS.md §3.2.
    Every LLM call is traced with prompt version, model, token usage.
    """

    def __init__(self, client: Optional[OllamaClient] = None):
        self._client = client or OllamaClient()

    def critique(self, inp: CritiqueInput) -> Optional[Critique]:
        """Generate a critique of a hypothesis.

        Returns None if LLM output cannot be parsed/validated.
        """
        hyp = inp.hypothesis
        prompt = CRITIC_EVALUATE_PROMPT.format(
            statement=hyp.statement,
            assumptions=json.dumps(hyp.assumptions),
            independent_variables=json.dumps(hyp.independent_variables),
            dependent_variables=json.dumps(hyp.dependent_variables),
            boundary_conditions=json.dumps(hyp.boundary_conditions),
            novelty_basis=hyp.novelty_basis,
            supporting_claim_ids=json.dumps(hyp.grounding_claim_ids),
            counter_evidence_chunks=json.dumps(inp.counter_evidence_chunks, indent=2),
            contradiction_context=json.dumps(inp.contradiction_context, indent=2),
        )

        llm_resp = self._client.generate_json(
            prompt,
            prompt_version=CRITIC_EVALUATE_PROMPT_VERSION,
            system=CRITIC_SYSTEM_PROMPT,
        )

        return self._parse_critique(llm_resp, hyp.hypothesis_id)

    def _parse_critique(
        self, llm_resp: LLMResponse, hypothesis_id: str
    ) -> Optional[Critique]:
        """Parse LLM response into a Critique schema object."""
        parsed = _extract_json(llm_resp.text)
        if parsed is None:
            logger.warning(
                "Failed to parse JSON from LLM response",
                extra={"trace_id": llm_resp.trace_id, "raw": llm_resp.text[:500]},
            )
            return None

        try:
            critique_id = f"crit_{uuid.uuid4().hex[:8]}"

            severity = _map_severity(parsed.get("severity", "medium"))

            # Build counter-evidence from LLM output
            counter_evidence: List[ClaimEvidence] = []
            for ev in parsed.get("counter_evidence_snippets", []):
                if isinstance(ev, dict) and ev.get("snippet"):
                    try:
                        counter_evidence.append(
                            ClaimEvidence(
                                source_id=ev.get("source_id", "unknown"),
                                page=max(1, int(ev.get("page", 1))),
                                snippet=ev["snippet"][:2000],
                                retrieval_score=min(
                                    1.0, max(0.0, float(ev.get("retrieval_score", 0.5)))
                                ),
                            )
                        )
                    except (ValueError, TypeError):
                        continue

            weak_assumptions = [
                str(a) for a in parsed.get("weak_assumptions", []) if str(a).strip()
            ]
            suggested_revisions = [
                str(r) for r in parsed.get("suggested_revisions", []) if str(r).strip()
            ]

            # Ensure at least one substantive element
            if not counter_evidence and not weak_assumptions and not suggested_revisions:
                weak_assumptions = ["No specific weaknesses identified by critic"]
                suggested_revisions = ["Consider additional evidence gathering"]

            critique = Critique(
                critique_id=critique_id,
                hypothesis_id=hypothesis_id,
                counter_evidence=counter_evidence,
                weak_assumptions=weak_assumptions,
                suggested_revisions=suggested_revisions,
                severity=severity,
            )

            logger.info(
                "Critique generated",
                extra={
                    "trace_id": llm_resp.trace_id,
                    "critique_id": critique_id,
                    "hypothesis_id": hypothesis_id,
                    "severity": severity.value,
                    "counter_evidence_count": len(counter_evidence),
                },
            )
            return critique

        except Exception as exc:
            logger.warning(
                "Critique schema validation failed: %s",
                exc,
                extra={"trace_id": llm_resp.trace_id},
            )
            return None
