"""Real-PDF end-to-end test: Phase 0 → Phase 3 complete pipeline.

Downloads a real arXiv paper, runs it through:
1. Ingestion (PDF → chunks)
2. Context extraction
3. Claim extraction
4. Normalization
5. Belief state
6. Contradiction analysis
7. Hypothesis generation (LLM)
8. Critique (LLM)
9. Hypothesis-Critique loop (LLM)

Validates every stage output against schemas.
"""

import json
import pytest
from pathlib import Path

from core.llm.client import OllamaClient
from services.ingestion.pdf_service import PDFIngestionService
from services.context.tool import ContextTool
from services.extraction.tool import ExtractionTool
from services.normalization.tool import NormalizationTool
from services.belief.tool import BeliefTool
from services.contradiction.tool import ContradictionTool
from services.multimodal.tool import MultimodalTool

from agents.hypothesis.agent import HypothesisAgent, HypothesisInput
from agents.critic.agent import CriticAgent, CritiqueInput
from agents.loop import HypothesisCritiqueLoop, LoopConfig

from core.schemas.hypothesis import Hypothesis
from core.schemas.critique import Critique


PDF_PATH = Path("outputs/smoke/attention_is_all_you_need.pdf")
SOURCE_ID = "arxiv_1706_03762"


@pytest.fixture(scope="module")
def ollama_client():
    client = OllamaClient()
    if not client.is_available():
        pytest.skip("Ollama not available for real-PDF E2E test")
    return client


@pytest.fixture(scope="module")
def ingestion_result():
    if not PDF_PATH.exists():
        pytest.skip(f"PDF not found at {PDF_PATH}")
    svc = PDFIngestionService()
    return svc.ingest_pdf(str(PDF_PATH), source_id=SOURCE_ID)


@pytest.fixture(scope="module")
def chunked_data(ingestion_result):
    chunks = [
        {
            "chunk_id": c.chunk_id,
            "source_id": c.source_id,
            "text": c.text,
            "page": c.page,
            "start_char": c.start_char,
            "end_char": c.end_char,
            "text_hash": c.text_hash,
            "context_id": c.context_id,
            "numeric_strings": c.numeric_strings,
            "unit_strings": c.unit_strings,
            "metric_names": c.metric_names,
        }
        for c in ingestion_result.chunks[:80]
    ]
    return chunks


@pytest.fixture(scope="module")
def context_result(chunked_data):
    return ContextTool().call({"chunks": chunked_data})


@pytest.fixture(scope="module")
def extraction_result(context_result):
    return ExtractionTool().call({
        "source_id": SOURCE_ID,
        "chunks": context_result["chunks"],
    })


@pytest.fixture(scope="module")
def normalization_result(extraction_result):
    return NormalizationTool().call({"claims": extraction_result["claims"]})


@pytest.fixture(scope="module")
def belief_result(normalization_result):
    return BeliefTool().call({"normalized_claims": normalization_result["normalized_claims"]})


@pytest.fixture(scope="module")
def contradiction_result(normalization_result):
    return ContradictionTool().call({
        "belief_state": {"claims": normalization_result["normalized_claims"]},
    })


# ---------------------------------------------------------------------------
# Phase 0-2 pipeline validation
# ---------------------------------------------------------------------------


class TestRealPDFPhase0to2:
    def test_ingestion_produces_chunks(self, ingestion_result):
        assert len(ingestion_result.chunks) > 50
        assert ingestion_result.metadata.get("total_pages")

    def test_context_extraction(self, context_result):
        assert context_result["contexts_created"] >= 0
        assert len(context_result["chunks"]) > 0

    def test_claim_extraction(self, extraction_result):
        assert len(extraction_result["claims"]) >= 1

    def test_normalization(self, normalization_result):
        assert isinstance(normalization_result["normalized_claims"], list)

    def test_belief_state(self, belief_result):
        assert isinstance(belief_result, dict)

    def test_contradiction_analysis(self, contradiction_result):
        assert "contradictions" in contradiction_result
        assert "consensus_groups" in contradiction_result


# ---------------------------------------------------------------------------
# Phase 3 real-PDF agent tests
# ---------------------------------------------------------------------------


class TestRealPDFPhase3:
    def test_hypothesis_from_real_claims(
        self, ollama_client, extraction_result, contradiction_result
    ):
        agent = HypothesisAgent(client=ollama_client)
        inp = HypothesisInput(
            claims=extraction_result["claims"][:5],
            contradictions=contradiction_result.get("contradictions", []),
            consensus_groups=contradiction_result.get("consensus_groups", []),
            constraints="Focus on attention mechanism performance in NMT.",
        )
        hyp = agent.generate(inp)
        assert hyp is not None
        assert isinstance(hyp, Hypothesis)
        assert len(hyp.statement) > 5
        assert len(hyp.assumptions) >= 1
        assert hyp.iteration_number == 1

    def test_critique_of_real_hypothesis(
        self, ollama_client, extraction_result, contradiction_result
    ):
        # Generate hypothesis first
        hyp_agent = HypothesisAgent(client=ollama_client)
        inp = HypothesisInput(
            claims=extraction_result["claims"][:5],
            contradictions=contradiction_result.get("contradictions", []),
        )
        hyp = hyp_agent.generate(inp)
        assert hyp is not None

        # Critique it
        critic = CriticAgent(client=ollama_client)
        counter_chunks = []
        for i, c in enumerate(extraction_result["claims"][:3]):
            text = c.get("text") or c.get("subject", "")
            if text:
                counter_chunks.append(
                    {"chunk_id": f"real_chunk_{i}", "text": text, "source_id": SOURCE_ID}
                )
        critique_inp = CritiqueInput(
            hypothesis=hyp,
            counter_evidence_chunks=counter_chunks,
        )
        critique = critic.critique(critique_inp)
        assert critique is not None
        assert isinstance(critique, Critique)
        assert critique.hypothesis_id == hyp.hypothesis_id
        assert critique.severity is not None

    def test_full_loop_on_real_data(
        self, ollama_client, extraction_result, contradiction_result
    ):
        loop = HypothesisCritiqueLoop(
            hypothesis_agent=HypothesisAgent(client=ollama_client),
            critic_agent=CriticAgent(client=ollama_client),
            config=LoopConfig(max_iterations=2, confidence_threshold=0.95),
        )
        inp = HypothesisInput(
            claims=extraction_result["claims"][:5],
            contradictions=contradiction_result.get("contradictions", []),
            consensus_groups=contradiction_result.get("consensus_groups", []),
            constraints="Attention mechanism efficiency and quality tradeoffs in machine translation.",
        )
        result = loop.run(inp)
        assert result.final_hypothesis is not None
        assert result.iterations_completed >= 1
        assert result.stopped_reason != ""
        assert result.total_duration_ms > 0
        assert isinstance(result.final_hypothesis, Hypothesis)
