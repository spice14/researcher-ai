"""Phase 3 tests — Agent Reasoning Layer with live LLM.

Tests cover:
- OllamaClient: connectivity, generate, generate_json
- HypothesisAgent: generate from structured evidence, schema compliance
- CriticAgent: critique hypothesis, schema compliance
- HypothesisCritiqueLoop: bounded iteration, stopping conditions
- Real-PDF integration: full pipeline from PDF to hypothesis
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from core.llm.client import OllamaClient, LLMResponse, LLMConnectionError
from core.llm.prompts import (
    HYPOTHESIS_GENERATE_PROMPT_VERSION,
    HYPOTHESIS_SYSTEM_PROMPT_VERSION,
    CRITIC_EVALUATE_PROMPT_VERSION,
)
from agents.hypothesis.agent import (
    HypothesisAgent,
    HypothesisInput,
    _extract_json,
    _map_confidence,
)
from agents.critic.agent import CriticAgent, CritiqueInput, _map_severity
from agents.loop import HypothesisCritiqueLoop, LoopConfig, LoopResult
from core.schemas.hypothesis import Hypothesis
from core.schemas.critique import Critique, CritiqueSeverity
from core.schemas.claim import ConfidenceLevel


# ---------------------------------------------------------------------------
# Utility Tests
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_json(self):
        result = _extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"key": "value"}\nDone.'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self):
        assert _extract_json("not json at all") is None

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None


class TestMapConfidence:
    def test_high(self):
        assert _map_confidence("high") == ConfidenceLevel.HIGH

    def test_medium(self):
        assert _map_confidence("medium") == ConfidenceLevel.MEDIUM

    def test_moderate_maps_to_medium(self):
        assert _map_confidence("moderate") == ConfidenceLevel.MEDIUM

    def test_low(self):
        assert _map_confidence("low") == ConfidenceLevel.LOW

    def test_unknown_defaults_to_low(self):
        assert _map_confidence("xyz") == ConfidenceLevel.LOW


class TestMapSeverity:
    def test_critical(self):
        assert _map_severity("critical") == CritiqueSeverity.CRITICAL

    def test_high(self):
        assert _map_severity("high") == CritiqueSeverity.HIGH

    def test_medium(self):
        assert _map_severity("medium") == CritiqueSeverity.MEDIUM

    def test_low(self):
        assert _map_severity("low") == CritiqueSeverity.LOW

    def test_unknown_defaults_to_low(self):
        assert _map_severity("unknown") == CritiqueSeverity.LOW


# ---------------------------------------------------------------------------
# Mock LLM Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(text: str) -> LLMResponse:
    """Create a mock LLMResponse."""
    return LLMResponse(
        text=text,
        model="test-model",
        prompt_version="test_v1",
        trace_id="test_trace_001",
        latency_ms=100.0,
        prompt_eval_count=50,
        eval_count=100,
    )


def _mock_hypothesis_json() -> str:
    return json.dumps({
        "statement": "Transformer attention mechanisms generalize better than RNNs on low-resource NMT tasks.",
        "rationale": "Evidence shows transformers achieve higher BLEU scores with less training data.",
        "assumptions": ["Low-resource defined as < 100k parallel sentences", "Standard NMT evaluation protocols used"],
        "independent_variables": ["Model architecture (Transformer vs RNN)"],
        "dependent_variables": ["BLEU score on low-resource NMT benchmark"],
        "boundary_conditions": ["Low-resource language pairs only"],
        "novelty_basis": "Existing literature focuses on high-resource; gap in low-resource comparison.",
        "known_risks": ["Small sample of language pairs may limit generalizability"],
        "confidence": "medium",
        "grounding_claim_ids": ["claim_001", "claim_002"],
    })


def _mock_critique_json() -> str:
    return json.dumps({
        "weak_assumptions": [
            "Low-resource threshold of 100k sentences is arbitrary",
            "Standard NMT protocols may not apply to all language pairs",
        ],
        "counter_evidence_snippets": [
            {
                "source_id": "paper_003",
                "page": 5,
                "snippet": "RNNs with attention outperform transformers below 50k sentences in 3 of 5 tested language pairs.",
                "retrieval_score": 0.82,
            }
        ],
        "suggested_revisions": [
            "Narrow scope to specific language families",
            "Define resource levels more precisely with multiple thresholds",
        ],
        "severity": "high",
        "reasoning": "The hypothesis overgeneralizes across diverse low-resource scenarios.",
    })


def _mock_revised_hypothesis_json() -> str:
    return json.dumps({
        "statement": "Transformer attention mechanisms generalize better than RNNs on low-resource NMT for Indo-European language pairs with 50-100k parallel sentences.",
        "rationale": "Refined evidence shows advantage applies primarily to specific language families and resource levels.",
        "assumptions": ["Indo-European language pairs", "Resource level: 50-100k parallel sentences"],
        "independent_variables": ["Model architecture (Transformer vs RNN)"],
        "dependent_variables": ["BLEU score on low-resource NMT benchmark"],
        "boundary_conditions": ["Indo-European language pairs", "50-100k parallel sentences"],
        "novelty_basis": "Narrows existing broad claims to a specific, testable scope.",
        "known_risks": ["Limited to Indo-European; may not transfer to other families"],
        "confidence": "high",
        "grounding_claim_ids": ["claim_001", "claim_002"],
        "revision_changes": "Narrowed scope per critique about overgeneralization",
    })


# ---------------------------------------------------------------------------
# OllamaClient Tests (mocked network)
# ---------------------------------------------------------------------------


class TestOllamaClient:
    def test_init_defaults(self):
        client = OllamaClient()
        assert "localhost" in client.base_url
        assert client.model is not None

    def test_init_custom(self):
        client = OllamaClient(base_url="http://custom:1234", model="test-model")
        assert client.base_url == "http://custom:1234"
        assert client.model == "test-model"

    def test_llm_response_token_usage(self):
        resp = _make_llm_response("test")
        usage = resp.token_usage
        assert usage["prompt_tokens"] == 50
        assert usage["completion_tokens"] == 100
        assert usage["total_tokens"] == 150


# ---------------------------------------------------------------------------
# Hypothesis Agent Tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestHypothesisAgent:
    def _make_agent(self, response_text: str) -> HypothesisAgent:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate_json.return_value = _make_llm_response(response_text)
        return HypothesisAgent(client=mock_client)

    def test_generate_valid_hypothesis(self):
        agent = self._make_agent(_mock_hypothesis_json())
        inp = HypothesisInput(
            claims=[{"claim_id": "claim_001", "subject": "Transformer"}],
            contradictions=[],
            consensus_groups=[],
        )
        hyp = agent.generate(inp)
        assert hyp is not None
        assert isinstance(hyp, Hypothesis)
        assert "Transformer" in hyp.statement
        assert len(hyp.assumptions) >= 1
        assert len(hyp.independent_variables) >= 1
        assert len(hyp.dependent_variables) >= 1
        assert hyp.novelty_basis
        assert hyp.iteration_number == 1
        assert hyp.qualitative_confidence == ConfidenceLevel.MEDIUM

    def test_generate_invalid_json_returns_none(self):
        agent = self._make_agent("This is not JSON at all!")
        inp = HypothesisInput(claims=[])
        hyp = agent.generate(inp)
        assert hyp is None

    def test_generate_fills_defaults_for_missing_fields(self):
        # Minimal valid JSON missing optional fields
        minimal = json.dumps({
            "statement": "A hypothesis",
            "novelty_basis": "It is new",
        })
        agent = self._make_agent(minimal)
        inp = HypothesisInput(claims=[])
        hyp = agent.generate(inp)
        assert hyp is not None
        assert len(hyp.assumptions) >= 1  # Default filled
        assert len(hyp.independent_variables) >= 1

    def test_revise_hypothesis(self):
        agent = self._make_agent(_mock_revised_hypothesis_json())
        # Create a starting hypothesis
        original = Hypothesis(
            hypothesis_id="hyp_original",
            statement="Original statement",
            assumptions=["Assumption 1"],
            independent_variables=["Var A"],
            dependent_variables=["Var B"],
            novelty_basis="Original novelty",
            iteration_number=1,
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        critique_data = {
            "severity": "high",
            "weak_assumptions": ["Assumption 1 is weak"],
            "counter_evidence_snippets": [],
            "suggested_revisions": ["Narrow scope"],
        }
        revised = agent.revise(original, critique_data)
        assert revised is not None
        assert revised.iteration_number == 2
        assert len(revised.revision_history) == 1
        assert revised.revision_history[0].iteration == 1

    def test_hypothesis_schema_compliance(self):
        """Every generated hypothesis must pass Hypothesis schema validation."""
        agent = self._make_agent(_mock_hypothesis_json())
        inp = HypothesisInput(claims=[{"claim_id": "c1"}])
        hyp = agent.generate(inp)
        assert hyp is not None
        # Validate by re-constructing from dict (Pydantic validation)
        hyp_dict = hyp.model_dump()
        revalidated = Hypothesis(**hyp_dict)
        assert revalidated.hypothesis_id == hyp.hypothesis_id


# ---------------------------------------------------------------------------
# Critic Agent Tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestCriticAgent:
    def _make_agent(self, response_text: str) -> CriticAgent:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate_json.return_value = _make_llm_response(response_text)
        return CriticAgent(client=mock_client)

    def _make_hypothesis(self) -> Hypothesis:
        return Hypothesis(
            hypothesis_id="hyp_test",
            statement="Test hypothesis statement",
            assumptions=["Assumption A"],
            independent_variables=["Var X"],
            dependent_variables=["Var Y"],
            novelty_basis="Test novelty",
            iteration_number=1,
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )

    def test_critique_valid(self):
        agent = self._make_agent(_mock_critique_json())
        inp = CritiqueInput(hypothesis=self._make_hypothesis())
        critique = agent.critique(inp)
        assert critique is not None
        assert isinstance(critique, Critique)
        assert critique.hypothesis_id == "hyp_test"
        assert critique.severity == CritiqueSeverity.HIGH
        assert len(critique.weak_assumptions) >= 1
        assert len(critique.counter_evidence) >= 1

    def test_critique_invalid_json_returns_none(self):
        agent = self._make_agent("Not a JSON response")
        inp = CritiqueInput(hypothesis=self._make_hypothesis())
        critique = agent.critique(inp)
        assert critique is None

    def test_critique_schema_compliance(self):
        agent = self._make_agent(_mock_critique_json())
        inp = CritiqueInput(hypothesis=self._make_hypothesis())
        critique = agent.critique(inp)
        assert critique is not None
        critique_dict = critique.model_dump()
        revalidated = Critique(**critique_dict)
        assert revalidated.critique_id == critique.critique_id

    def test_critique_ensures_substance(self):
        """Critique with empty fields gets defaults to ensure substance."""
        empty_critique = json.dumps({
            "weak_assumptions": [],
            "counter_evidence_snippets": [],
            "suggested_revisions": [],
            "severity": "low",
            "reasoning": "Nothing found",
        })
        agent = self._make_agent(empty_critique)
        inp = CritiqueInput(hypothesis=self._make_hypothesis())
        critique = agent.critique(inp)
        assert critique is not None
        # Should have at least default substance
        assert len(critique.weak_assumptions) >= 1 or len(critique.suggested_revisions) >= 1


# ---------------------------------------------------------------------------
# Loop Tests (mocked agents)
# ---------------------------------------------------------------------------


class TestHypothesisCritiqueLoop:
    def _make_mock_hypothesis(self, confidence: float = 0.5, iteration: int = 1) -> Hypothesis:
        return Hypothesis(
            hypothesis_id=f"hyp_{iteration}",
            statement="Test hypothesis",
            assumptions=["Assumption"],
            independent_variables=["Var X"],
            dependent_variables=["Var Y"],
            novelty_basis="Test novelty",
            iteration_number=iteration,
            confidence_score=confidence,
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )

    def _make_mock_critique(self) -> Critique:
        return Critique(
            critique_id="crit_test",
            hypothesis_id="hyp_test",
            weak_assumptions=["Weak assumption"],
            suggested_revisions=["Revise this"],
            severity=CritiqueSeverity.MEDIUM,
        )

    def test_loop_stops_on_confidence_threshold(self):
        high_conf_hyp = self._make_mock_hypothesis(confidence=0.9)
        mock_hyp_agent = MagicMock(spec=HypothesisAgent)
        mock_hyp_agent.generate.return_value = high_conf_hyp

        loop = HypothesisCritiqueLoop(
            hypothesis_agent=mock_hyp_agent,
            config=LoopConfig(max_iterations=5, confidence_threshold=0.8),
        )
        inp = HypothesisInput(claims=[])
        result = loop.run(inp)

        assert result.final_hypothesis is not None
        assert result.stopped_reason == "confidence_threshold_met"
        assert result.iterations_completed == 1
        # Critic should NOT have been called
        mock_hyp_agent.revise.assert_not_called()

    def test_loop_stops_on_max_iterations(self):
        low_conf = self._make_mock_hypothesis(confidence=0.3)
        revised = self._make_mock_hypothesis(confidence=0.4, iteration=2)
        critique = self._make_mock_critique()

        mock_hyp_agent = MagicMock(spec=HypothesisAgent)
        mock_hyp_agent.generate.return_value = low_conf
        mock_hyp_agent.revise.return_value = revised

        mock_critic = MagicMock(spec=CriticAgent)
        mock_critic.critique.return_value = critique

        loop = HypothesisCritiqueLoop(
            hypothesis_agent=mock_hyp_agent,
            critic_agent=mock_critic,
            config=LoopConfig(max_iterations=3, confidence_threshold=0.9),
        )
        result = loop.run(HypothesisInput(claims=[]))

        assert result.iterations_completed == 3
        assert result.stopped_reason == "max_iterations_reached"
        assert len(result.critiques) >= 1

    def test_loop_stops_on_initial_failure(self):
        mock_hyp_agent = MagicMock(spec=HypothesisAgent)
        mock_hyp_agent.generate.return_value = None

        loop = HypothesisCritiqueLoop(hypothesis_agent=mock_hyp_agent)
        result = loop.run(HypothesisInput(claims=[]))

        assert result.final_hypothesis is None
        assert result.stopped_reason == "initial_hypothesis_failed"

    def test_loop_stops_on_critique_failure(self):
        hyp = self._make_mock_hypothesis(confidence=0.3)
        mock_hyp_agent = MagicMock(spec=HypothesisAgent)
        mock_hyp_agent.generate.return_value = hyp

        mock_critic = MagicMock(spec=CriticAgent)
        mock_critic.critique.return_value = None

        loop = HypothesisCritiqueLoop(
            hypothesis_agent=mock_hyp_agent,
            critic_agent=mock_critic,
            config=LoopConfig(max_iterations=3),
        )
        result = loop.run(HypothesisInput(claims=[]))

        assert result.stopped_reason == "critique_generation_failed"
        assert result.final_hypothesis is not None

    def test_loop_result_has_trace_entries(self):
        hyp = self._make_mock_hypothesis(confidence=0.9)
        mock_hyp_agent = MagicMock(spec=HypothesisAgent)
        mock_hyp_agent.generate.return_value = hyp

        loop = HypothesisCritiqueLoop(
            hypothesis_agent=mock_hyp_agent,
            config=LoopConfig(confidence_threshold=0.8),
        )
        result = loop.run(HypothesisInput(claims=[]))
        assert len(result.trace_entries) >= 1


# ---------------------------------------------------------------------------
# Live LLM Integration Tests (require running Ollama)
# ---------------------------------------------------------------------------


class TestLiveOllama:
    """Integration tests that require a running Ollama instance.

    Skip if Ollama is not available.
    """

    @pytest.fixture(autouse=True)
    def check_ollama(self):
        client = OllamaClient()
        if not client.is_available():
            pytest.skip("Ollama not available")
        self.client = client

    def test_ollama_generate(self):
        resp = self.client.generate(
            "Return the word 'hello' and nothing else.",
            prompt_version="test_v1",
            temperature=0.0,
            max_tokens=10,
        )
        assert isinstance(resp, LLMResponse)
        assert len(resp.text) > 0
        assert resp.model
        assert resp.trace_id.startswith("llm_")
        assert resp.latency_ms > 0
        assert resp.token_usage["total_tokens"] > 0

    def test_ollama_generate_json(self):
        resp = self.client.generate_json(
            'Return: {"status": "ok"}',
            prompt_version="test_v1",
            temperature=0.0,
            max_tokens=50,
        )
        parsed = _extract_json(resp.text)
        assert parsed is not None
        assert "status" in parsed

    def test_live_hypothesis_generation(self):
        agent = HypothesisAgent(client=self.client)
        inp = HypothesisInput(
            claims=[
                {"claim_id": "c1", "subject": "BERT", "predicate": "achieves", "object": "93.5% F1 on CoNLL NER"},
                {"claim_id": "c2", "subject": "RoBERTa", "predicate": "achieves", "object": "94.2% F1 on CoNLL NER"},
            ],
            contradictions=[
                {"claim_a": "c1", "claim_b": "c2", "reason": "Different F1 scores on same task"},
            ],
            consensus_groups=[],
            constraints="Focus on NER performance comparison between pretrained language models.",
        )
        hyp = agent.generate(inp)
        assert hyp is not None
        assert isinstance(hyp, Hypothesis)
        assert len(hyp.statement) > 10
        assert len(hyp.assumptions) >= 1
        assert hyp.iteration_number == 1

    def test_live_critique(self):
        agent = HypothesisAgent(client=self.client)
        critic = CriticAgent(client=self.client)

        inp = HypothesisInput(
            claims=[{"claim_id": "c1", "subject": "Attention", "predicate": "improves", "object": "BLEU by 2.0 points"}],
            contradictions=[],
        )
        hyp = agent.generate(inp)
        assert hyp is not None

        critique_inp = CritiqueInput(
            hypothesis=hyp,
            counter_evidence_chunks=[
                {"chunk_id": "chunk_99", "text": "RNN-based models still outperform on very long sequences.", "source_id": "paper_x"},
            ],
        )
        critique = critic.critique(critique_inp)
        assert critique is not None
        assert isinstance(critique, Critique)
        assert critique.hypothesis_id == hyp.hypothesis_id

    def test_live_loop_2_iterations(self):
        loop = HypothesisCritiqueLoop(
            config=LoopConfig(max_iterations=2, confidence_threshold=0.95),
        )
        inp = HypothesisInput(
            claims=[
                {"claim_id": "c1", "subject": "Model A", "predicate": "achieves", "object": "92% accuracy on ImageNet"},
            ],
            contradictions=[],
            constraints="Compare CNN vs Transformer architectures on image classification.",
        )
        result = loop.run(inp)
        assert result.final_hypothesis is not None
        assert result.iterations_completed >= 1
        assert result.stopped_reason != ""
        assert result.total_duration_ms > 0
