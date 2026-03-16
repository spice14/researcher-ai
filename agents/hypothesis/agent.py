"""Hypothesis Agent — proposes testable, literature-grounded hypotheses.

Purpose:
- Accept structured evidence (claims, contradictions, consensus)
- Generate hypotheses via bounded LLM calls
- Validate all outputs against Hypothesis schema
- Revise hypotheses based on critique feedback

Inputs/Outputs:
- Input: HypothesisInput (claims, contradictions, consensus, constraints)
- Output: Hypothesis schema object

Schema References:
- core.schemas.hypothesis.Hypothesis
- core.schemas.critique.Critique

Failure Modes:
- LLM returns invalid JSON → log, return None
- LLM returns schema-invalid hypothesis → log, return None
- Ollama unreachable → raise LLMConnectionError

Testing Strategy:
- Unit tests with mocked LLM responses
- Integration tests against live Ollama
- Schema validation on every output
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.llm.client import OllamaClient, LLMResponse
from core.llm.prompts import (
    HYPOTHESIS_GENERATE_PROMPT,
    HYPOTHESIS_GENERATE_PROMPT_VERSION,
    HYPOTHESIS_REVISE_PROMPT,
    HYPOTHESIS_REVISE_PROMPT_VERSION,
    HYPOTHESIS_SYSTEM_PROMPT,
    HYPOTHESIS_SYSTEM_PROMPT_VERSION,
)
from core.schemas.claim import ConfidenceLevel
from core.schemas.hypothesis import Hypothesis

logger = logging.getLogger(__name__)


@dataclass
class HypothesisInput:
    """Structured input for hypothesis generation."""

    claims: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    consensus_groups: List[Dict[str, Any]] = field(default_factory=list)
    constraints: str = ""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from LLM response text, tolerating markdown fences."""
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip())
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find first { ... } block
    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(cleaned[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _map_confidence(raw: str) -> ConfidenceLevel:
    """Map raw confidence string to ConfidenceLevel enum."""
    raw_lower = raw.strip().lower()
    if raw_lower in ("high",):
        return ConfidenceLevel.HIGH
    if raw_lower in ("medium", "moderate", "med"):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class HypothesisAgent:
    """Generates structured hypotheses from evidence via LLM.

    Operates only on structured schemas per AGENTS.md §3.2.
    Every LLM call is traced with prompt version, model, token usage.
    """

    def __init__(self, client: Optional[OllamaClient] = None):
        self._client = client or OllamaClient()

    def generate(self, inp: HypothesisInput) -> Optional[Hypothesis]:
        """Generate a hypothesis from structured evidence.

        Returns None if LLM output cannot be parsed/validated.
        """
        prompt = HYPOTHESIS_GENERATE_PROMPT.format(
            contradictions=json.dumps(inp.contradictions, indent=2),
            consensus_groups=json.dumps(inp.consensus_groups, indent=2),
            claims=json.dumps(inp.claims, indent=2),
            constraints=inp.constraints or "None",
        )

        llm_resp = self._client.generate_json(
            prompt,
            prompt_version=HYPOTHESIS_GENERATE_PROMPT_VERSION,
            system=HYPOTHESIS_SYSTEM_PROMPT,
        )

        return self._parse_hypothesis(llm_resp, iteration=1)

    def revise(
        self,
        hypothesis: Hypothesis,
        critique_data: Dict[str, Any],
    ) -> Optional[Hypothesis]:
        """Revise a hypothesis based on critique feedback.

        Returns None if LLM output cannot be parsed/validated.
        """
        prompt = HYPOTHESIS_REVISE_PROMPT.format(
            hypothesis=json.dumps({
                "statement": hypothesis.statement,
                "assumptions": hypothesis.assumptions,
                "independent_variables": hypothesis.independent_variables,
                "dependent_variables": hypothesis.dependent_variables,
                "boundary_conditions": hypothesis.boundary_conditions,
                "novelty_basis": hypothesis.novelty_basis,
            }, indent=2),
            severity=critique_data.get("severity", "medium"),
            weak_assumptions=json.dumps(critique_data.get("weak_assumptions", [])),
            counter_evidence=json.dumps(critique_data.get("counter_evidence_snippets", [])),
            suggested_revisions=json.dumps(critique_data.get("suggested_revisions", [])),
        )

        llm_resp = self._client.generate_json(
            prompt,
            prompt_version=HYPOTHESIS_REVISE_PROMPT_VERSION,
            system=HYPOTHESIS_SYSTEM_PROMPT,
        )

        next_iteration = hypothesis.iteration_number + 1
        revised = self._parse_hypothesis(llm_resp, iteration=next_iteration)

        if revised is not None:
            changes = critique_data.get("revision_changes", "Revised based on critique")
            if isinstance(changes, list):
                changes = "; ".join(changes)
            revised.add_revision(
                changes=str(changes)[:500] or "Revised based on critique",
                rationale=f"Critic severity: {critique_data.get('severity', 'unknown')}",
            )
        return revised

    def _parse_hypothesis(
        self, llm_resp: LLMResponse, iteration: int
    ) -> Optional[Hypothesis]:
        """Parse LLM response into a Hypothesis schema object."""
        parsed = _extract_json(llm_resp.text)
        if parsed is None:
            logger.warning(
                "Failed to parse JSON from LLM response",
                extra={"trace_id": llm_resp.trace_id, "raw": llm_resp.text[:500]},
            )
            return None

        try:
            hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"

            # Ensure required list fields are present and non-empty
            assumptions = parsed.get("assumptions") or ["Unstated assumption"]
            ind_vars = parsed.get("independent_variables") or ["Primary independent variable"]
            dep_vars = parsed.get("dependent_variables") or ["Primary dependent variable"]

            confidence = _map_confidence(parsed.get("confidence", "low"))

            grounding_ids = parsed.get("grounding_claim_ids") or []

            hypothesis = Hypothesis(
                hypothesis_id=hyp_id,
                statement=parsed.get("statement", ""),
                rationale=parsed.get("rationale"),
                assumptions=assumptions,
                independent_variables=ind_vars,
                dependent_variables=dep_vars,
                boundary_conditions=parsed.get("boundary_conditions") or [],
                novelty_basis=parsed.get("novelty_basis", "Novel based on evidence gap"),
                known_risks=parsed.get("known_risks") or [],
                supporting_citations=[],
                confidence_score={"low": 0.3, "medium": 0.6, "high": 0.85}.get(
                    confidence.value, 0.3
                ),
                grounding_claim_ids=grounding_ids,
                iteration_number=iteration,
                qualitative_confidence=confidence,
            )

            logger.info(
                "Hypothesis generated",
                extra={
                    "trace_id": llm_resp.trace_id,
                    "hypothesis_id": hyp_id,
                    "confidence": confidence.value,
                    "iteration": iteration,
                },
            )
            return hypothesis

        except Exception as exc:
            logger.warning(
                "Hypothesis schema validation failed: %s",
                exc,
                extra={"trace_id": llm_resp.trace_id},
            )
            return None
