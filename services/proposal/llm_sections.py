"""LLM-backed section generators for research proposals.

Generates richer proposal sections using Ollama when available,
falling back to deterministic generation from structured inputs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _truncate(text: str, max_chars: int = 2000) -> str:
    return text[:max_chars] + "..." if len(text) > max_chars else text


class LLMSectionGenerator:
    """Generates proposal sections using LLM with deterministic fallback."""

    def __init__(self, llm_client=None) -> None:
        self._llm = llm_client

    def generate_novelty(self, hypothesis: str, claims: List[Dict], critiques: List[Dict]) -> str:
        """Generate the novelty statement section."""
        if self._llm and self._llm_available():
            prompt = (
                f"Write a compelling research novelty statement for this hypothesis:\n\n"
                f"HYPOTHESIS: {hypothesis}\n\n"
                f"SUPPORTING CLAIMS: {json.dumps(claims[:5], indent=2)}\n\n"
                f"IDENTIFIED GAPS (from critiques): "
                f"{json.dumps([c.get('weak_assumptions', []) for c in critiques[:3]], indent=2)}\n\n"
                "Write 2-3 paragraphs explaining what gap this fills, why it matters, "
                "and what is novel. Be specific and grounded in the evidence."
            )
            result = self._call_llm(prompt)
            if result:
                return result

        # Deterministic fallback
        lines = [f"**Hypothesis:** {hypothesis}", ""]
        if claims:
            lines.append(
                f"This hypothesis is grounded in {len(claims)} supporting claims "
                "from the literature."
            )
        if critiques:
            gaps = []
            for c in critiques:
                gaps.extend(c.get("weak_assumptions", []))
            if gaps:
                lines.append("\n**Gaps addressed:**")
                lines.extend(f"- {g}" for g in gaps[:5])
        return "\n".join(lines)

    def generate_methodology(
        self,
        hypothesis: str,
        assumptions: List[str],
        variables: Dict[str, List[str]],
        evidence_tables: Optional[List[Dict]] = None,
    ) -> str:
        """Generate the methodology section."""
        if self._llm and self._llm_available():
            prompt = (
                f"Write a methodology section for a research proposal.\n\n"
                f"HYPOTHESIS: {hypothesis}\n"
                f"ASSUMPTIONS: {json.dumps(assumptions)}\n"
                f"INDEPENDENT VARIABLES: {json.dumps(variables.get('independent', []))}\n"
                f"DEPENDENT VARIABLES: {json.dumps(variables.get('dependent', []))}\n"
                + (
                    f"EVIDENCE TABLES: {json.dumps([t.get('caption') for t in (evidence_tables or [])[:3]])}\n"
                    if evidence_tables
                    else ""
                )
                + "\nWrite 2-3 paragraphs describing a concrete experimental design, "
                "evaluation metrics, and validation approach."
            )
            result = self._call_llm(prompt)
            if result:
                return result

        # Deterministic fallback
        lines = ["**Experimental Design**", ""]
        if variables.get("independent"):
            lines.append(f"**Independent variables:** {', '.join(variables['independent'])}")
        if variables.get("dependent"):
            lines.append(f"**Dependent variables:** {', '.join(variables['dependent'])}")
        if assumptions:
            lines.append("\n**Assumptions:**")
            lines.extend(f"- {a}" for a in assumptions[:5])
        if evidence_tables:
            lines.append(f"\n*{len(evidence_tables)} evidence table(s) available.*")
        return "\n".join(lines)

    def generate_expected_outcomes(
        self, hypothesis: str, risks: List[str], beliefs: List[Dict]
    ) -> str:
        """Generate the expected outcomes section."""
        if self._llm and self._llm_available():
            prompt = (
                f"Write an expected outcomes section for a research proposal.\n\n"
                f"HYPOTHESIS: {hypothesis}\n"
                f"KNOWN RISKS: {json.dumps(risks)}\n"
                f"BELIEF STATES: {json.dumps(beliefs[:5], indent=2)}\n\n"
                "Write 2 paragraphs: (1) predicted positive outcomes and significance, "
                "(2) risk mitigation strategies."
            )
            result = self._call_llm(prompt)
            if result:
                return result

        # Deterministic fallback
        lines = []
        if beliefs:
            consensus = [b for b in beliefs if b.get("status") == "consensus"]
            contested = [b for b in beliefs if b.get("status") == "contested"]
            lines.append(
                f"Expected outcomes are grounded in {len(beliefs)} belief states: "
                f"{len(consensus)} consensus, {len(contested)} contested."
            )
        if risks:
            lines.append("\n**Known risks:**")
            lines.extend(f"- {r}" for r in risks[:5])
        return "\n".join(lines) if lines else "Outcomes to be determined based on experimental results."

    def _llm_available(self) -> bool:
        try:
            return self._llm.is_available()
        except Exception:
            return False

    def _call_llm(self, prompt: str) -> Optional[str]:
        try:
            response = self._llm.generate(prompt)
            if isinstance(response, dict):
                return response.get("response") or response.get("text")
            return str(response) if response else None
        except Exception as exc:
            logger.warning("LLM section generation failed: %s", exc)
            return None
