"""Bounded hypothesis-critique iteration loop.

Purpose:
- Coordinate Hypothesis Agent and Critic Agent in an adversarial loop
- Enforce iteration bounds and confidence thresholds
- Produce a final hypothesis with full revision history

Inputs/Outputs:
- Input: LoopConfig + HypothesisInput + optional RAG chunks
- Output: LoopResult with final hypothesis, all critiques, trace metadata

Failure Modes:
- Both agents fail to produce output → return partial result
- Max iterations reached → return best hypothesis so far
- LLM unreachable → propagate error

Testing Strategy:
- Unit tests with mocked agents
- Integration tests with live LLM
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.critic.agent import CriticAgent, CritiqueInput
from agents.hypothesis.agent import HypothesisAgent, HypothesisInput
from core.schemas.critique import Critique
from core.schemas.hypothesis import Hypothesis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoopConfig:
    """Configuration for bounded agent iteration."""

    max_iterations: int = 5
    confidence_threshold: float = 0.8


@dataclass
class LoopResult:
    """Result of a hypothesis-critique iteration loop."""

    final_hypothesis: Optional[Hypothesis] = None
    critiques: List[Critique] = field(default_factory=list)
    iterations_completed: int = 0
    stopped_reason: str = ""
    trace_entries: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_ms: float = 0.0


class HypothesisCritiqueLoop:
    """Bounded adversarial loop between Hypothesis and Critic agents.

    The orchestrator manages this loop per IMPLEMENTATION_PLAN §3.3:
    1. Hypothesis Agent proposes → Critic Agent challenges
    2. Hypothesis Agent revises using critique
    3. Repeat until confidence_score >= threshold OR max_iterations reached
    4. Return final hypothesis with full revision history
    """

    def __init__(
        self,
        hypothesis_agent: Optional[HypothesisAgent] = None,
        critic_agent: Optional[CriticAgent] = None,
        config: Optional[LoopConfig] = None,
    ):
        self._hyp_agent = hypothesis_agent or HypothesisAgent()
        self._critic_agent = critic_agent or CriticAgent()
        self._config = config or LoopConfig()

    def run(
        self,
        inp: HypothesisInput,
        counter_evidence_chunks: Optional[List[Dict[str, Any]]] = None,
        contradiction_context: Optional[List[Dict[str, Any]]] = None,
    ) -> LoopResult:
        """Execute the hypothesis-critique loop.

        Args:
            inp: Structured evidence input for hypothesis generation.
            counter_evidence_chunks: RAG chunks for critic to use.
            contradiction_context: Contradiction data for critic context.

        Returns:
            LoopResult with final hypothesis and all critiques.
        """
        start = time.time()
        result = LoopResult()
        counter_chunks = counter_evidence_chunks or []
        contra_ctx = contradiction_context or []

        # Step 1: Initial hypothesis
        logger.info("Loop starting: generating initial hypothesis")
        hypothesis = self._hyp_agent.generate(inp)

        if hypothesis is None:
            result.stopped_reason = "initial_hypothesis_failed"
            result.total_duration_ms = (time.time() - start) * 1000
            logger.warning("Loop stopped: initial hypothesis generation failed")
            return result

        result.final_hypothesis = hypothesis
        result.iterations_completed = 1

        result.trace_entries.append({
            "iteration": 1,
            "action": "generate",
            "hypothesis_id": hypothesis.hypothesis_id,
            "confidence": hypothesis.confidence_score,
        })

        # Check if already meets threshold
        if (hypothesis.confidence_score or 0) >= self._config.confidence_threshold:
            result.stopped_reason = "confidence_threshold_met"
            result.total_duration_ms = (time.time() - start) * 1000
            logger.info("Loop stopped: confidence threshold met on first hypothesis")
            return result

        # Steps 2..N: Critique-revise loop
        for iteration in range(2, self._config.max_iterations + 1):
            logger.info("Loop iteration %d: critiquing hypothesis", iteration)

            # Critique
            critique_input = CritiqueInput(
                hypothesis=hypothesis,
                counter_evidence_chunks=counter_chunks,
                contradiction_context=contra_ctx,
            )
            critique = self._critic_agent.critique(critique_input)

            if critique is None:
                result.stopped_reason = "critique_generation_failed"
                result.trace_entries.append({
                    "iteration": iteration,
                    "action": "critique_failed",
                })
                break

            result.critiques.append(critique)
            result.trace_entries.append({
                "iteration": iteration,
                "action": "critique",
                "critique_id": critique.critique_id,
                "severity": critique.severity.value,
            })

            # Revise
            logger.info("Loop iteration %d: revising hypothesis", iteration)
            critique_data = {
                "severity": critique.severity.value,
                "weak_assumptions": critique.weak_assumptions,
                "counter_evidence_snippets": [
                    {
                        "source_id": ev.source_id,
                        "page": ev.page,
                        "snippet": ev.snippet,
                        "retrieval_score": ev.retrieval_score,
                    }
                    for ev in critique.counter_evidence
                ],
                "suggested_revisions": critique.suggested_revisions,
            }

            revised = self._hyp_agent.revise(hypothesis, critique_data)

            if revised is None:
                result.stopped_reason = "revision_failed"
                result.trace_entries.append({
                    "iteration": iteration,
                    "action": "revision_failed",
                })
                break

            hypothesis = revised
            result.final_hypothesis = hypothesis
            result.iterations_completed = iteration

            result.trace_entries.append({
                "iteration": iteration,
                "action": "revise",
                "hypothesis_id": hypothesis.hypothesis_id,
                "confidence": hypothesis.confidence_score,
            })

            # Check confidence threshold
            if (hypothesis.confidence_score or 0) >= self._config.confidence_threshold:
                result.stopped_reason = "confidence_threshold_met"
                break
        else:
            result.stopped_reason = "max_iterations_reached"

        result.total_duration_ms = (time.time() - start) * 1000
        logger.info(
            "Loop completed: %d iterations, reason=%s",
            result.iterations_completed,
            result.stopped_reason,
        )
        return result
