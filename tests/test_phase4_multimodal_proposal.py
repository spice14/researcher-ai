"""Tests for Phase 4: multimodal extraction and LLM-backed proposal."""

from __future__ import annotations

import pytest
from pathlib import Path


class TestLatexRenderer:
    """Tests for LaTeX rendering."""

    def test_render_basic_proposal(self):
        from services.proposal.latex_renderer import render_proposal, escape_latex

        latex = render_proposal(
            title="Test Proposal",
            sections=[
                {"heading": "Novelty", "content": "This is novel because **deep learning**."},
                {"heading": "Methodology", "content": "- Step 1\n- Step 2"},
            ],
            references=[
                {"paper_id": "paper001", "title": "Deep Learning", "authors": ["LeCun"], "doi": "10.1/dl"}
            ],
        )
        assert r"\documentclass" in latex
        assert "Test Proposal" in latex
        assert r"\section{Novelty}" in latex
        assert r"\textbf{deep learning}" in latex
        assert r"\bibitem{paper001}" in latex

    def test_escape_latex(self):
        from services.proposal.latex_renderer import escape_latex

        result = escape_latex("100% & <test>")
        assert r"\%" in result
        assert r"\&" in result

    def test_render_with_evidence_tables(self):
        from services.proposal.latex_renderer import render_proposal

        latex = render_proposal(
            title="Proposal With Tables",
            sections=[],
            references=[],
            evidence_tables=[
                {
                    "caption": "Results Table",
                    "headers": ["Method", "F1"],
                    "rows": [{"Method": "Ours", "F1": "0.92"}],
                }
            ],
        )
        assert "Evidence Tables" in latex
        assert "Results Table" in latex
        assert "Method" in latex


class TestLLMSections:
    """Tests for LLM section generator fallback."""

    def test_generate_novelty_fallback(self):
        from services.proposal.llm_sections import LLMSectionGenerator

        gen = LLMSectionGenerator(llm_client=None)
        result = gen.generate_novelty(
            "Hypothesis: X improves Y",
            [{"text": "claim 1"}],
            [{"weak_assumptions": ["assumption A"]}],
        )
        assert "X improves Y" in result or "Hypothesis" in result

    def test_generate_methodology_fallback(self):
        from services.proposal.llm_sections import LLMSectionGenerator

        gen = LLMSectionGenerator(llm_client=None)
        result = gen.generate_methodology(
            "Test hypothesis",
            ["assumption 1"],
            {"independent": ["var A"], "dependent": ["var B"]},
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_outcomes_fallback(self):
        from services.proposal.llm_sections import LLMSectionGenerator

        gen = LLMSectionGenerator(llm_client=None)
        result = gen.generate_expected_outcomes(
            "Test hypothesis",
            ["risk 1", "risk 2"],
            [{"metric_canonical": "f1", "status": "consensus"}],
        )
        assert isinstance(result, str)


class TestMultimodalPDFExtraction:
    """Tests for multimodal PDF extraction."""

    PDF_PATH = "tests/fixtures/real_paper_arxiv.pdf"

    def test_extract_from_pdf_no_pymupdf(self, tmp_path):
        """Should return empty list gracefully when PyMuPDF unavailable."""
        from services.multimodal.service import MultimodalExtractionService

        svc = MultimodalExtractionService()
        # If PyMuPDF is not installed, returns empty list
        try:
            import fitz
            results = svc.extract_from_pdf(self.PDF_PATH, "test_paper")
            assert isinstance(results, list)
        except ImportError:
            results = svc.extract_from_pdf(self.PDF_PATH, "test_paper")
            assert results == []

    def test_extract_from_pdf_with_fixture(self):
        """Test extraction from real PDF fixture."""
        if not Path(self.PDF_PATH).exists():
            pytest.skip("PDF fixture not available")

        from services.multimodal.service import MultimodalExtractionService

        svc = MultimodalExtractionService()
        results = svc.extract_from_pdf(self.PDF_PATH, "test_paper")
        assert isinstance(results, list)

    def test_multimodal_tool_with_pdf_path(self):
        """MultimodalTool should support pdf_path parameter."""
        from services.multimodal.tool import MultimodalTool

        tool = MultimodalTool()
        m = tool.manifest()
        assert "pdf_path" in m.input_schema["properties"]
        assert "link_to_claims" in m.input_schema["properties"]


class TestProposalWithLaTeX:
    """Tests for proposal service with LaTeX export."""

    def _make_request(self, export_format: str = "md"):
        from services.proposal.schemas import ProposalRequest

        return ProposalRequest(
            hypothesis_id="hyp_001",
            statement="Test hypothesis statement",
            rationale="Grounded in evidence",
            assumptions=["Assumption 1"],
            supporting_claims=[{"text": "claim 1", "paper_id": "p1"}],
            paper_references=[{"paper_id": "p1", "title": "Paper 1", "authors": ["Author A"], "doi": "10.1/test"}],
            export_format=export_format,
        )

    def test_generate_markdown(self):
        from services.proposal.service import ProposalService

        svc = ProposalService()
        result = svc.generate(self._make_request("md"))
        assert result.proposal_id.startswith("proposal_")
        assert result.latex_output is None
        assert "Test hypothesis" in result.full_markdown

    def test_generate_latex(self):
        from services.proposal.service import ProposalService

        svc = ProposalService()
        result = svc.generate(self._make_request("latex"))
        assert result.latex_output is not None
        assert r"\documentclass" in result.latex_output
        assert "Test hypothesis" in result.latex_output

    def test_evidence_tables_embedded(self):
        from services.proposal.service import ProposalService
        from services.proposal.schemas import ProposalRequest

        req = ProposalRequest(
            hypothesis_id="hyp_002",
            statement="Another hypothesis",
            evidence_tables=[
                {"caption": "Results", "headers": ["Model", "F1"], "rows": [{"Model": "Ours", "F1": "0.85"}]}
            ],
        )
        svc = ProposalService()
        result = svc.generate(req)
        assert result.evidence_tables
        assert result.evidence_tables[0]["caption"] == "Results"
