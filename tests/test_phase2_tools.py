"""Phase 2 tests — MCP tool wrappers for all services.

Tests cover:
- RAGTool: retrieval via MCP interface
- ContextTool: context extraction via MCP interface
- ProposalTool: proposal generation via MCP interface
- MultimodalTool: multimodal extraction via MCP interface
- Full registry: all 9 tools register without conflicts
- Pipeline validation: core pipeline validates
- Tool contract enforcement: manifests, input/output schemas
"""

import pytest
from datetime import datetime, UTC

from core.mcp import MCPRegistry


# ---------------------------------------------------------------------------
# RAG Tool Tests
# ---------------------------------------------------------------------------

class TestRAGTool:
    """Tests for RAG MCP tool wrapper."""

    def _make_tool(self):
        from services.rag.tool import RAGTool
        return RAGTool()

    def test_manifest_valid(self):
        tool = self._make_tool()
        m = tool.manifest()
        assert m.name == "rag"
        assert m.version == "1.0.0"
        assert m.deterministic is True
        assert "query" in m.input_schema["required"]
        assert "corpus" in m.input_schema["required"]

    def test_retrieve_with_matches(self):
        tool = self._make_tool()
        result = tool.call({
            "query": "accuracy on ImageNet",
            "corpus": [
                {
                    "chunk_id": "c1",
                    "source_id": "paper_001",
                    "text": "We achieve 95% accuracy on ImageNet classification.",
                },
                {
                    "chunk_id": "c2",
                    "source_id": "paper_001",
                    "text": "The model uses transformer architecture.",
                },
            ],
            "top_k": 5,
        })
        assert result["query"] == "accuracy on ImageNet"
        assert result["retrieval_method"] == "lexical_overlap_v1"
        assert len(result["matches"]) >= 1
        # First match should be the one mentioning accuracy and ImageNet
        assert result["matches"][0]["chunk_id"] == "c1"
        assert result["matches"][0]["score"] > 0

    def test_retrieve_empty_corpus(self):
        tool = self._make_tool()
        result = tool.call({
            "query": "test query",
            "corpus": [],
        })
        assert result["matches"] == []
        assert len(result["warnings"]) > 0

    def test_retrieve_with_source_filter(self):
        tool = self._make_tool()
        result = tool.call({
            "query": "accuracy",
            "corpus": [
                {"chunk_id": "c1", "source_id": "paper_001", "text": "accuracy is 95%"},
                {"chunk_id": "c2", "source_id": "paper_002", "text": "accuracy is 90%"},
            ],
            "source_ids": ["paper_001"],
        })
        for m in result["matches"]:
            assert m["source_id"] == "paper_001"

    def test_missing_query_raises(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="query is required"):
            tool.call({"corpus": []})

    def test_deterministic_output(self):
        tool = self._make_tool()
        payload = {
            "query": "accuracy",
            "corpus": [
                {"chunk_id": "c1", "source_id": "p1", "text": "accuracy is 95%"},
                {"chunk_id": "c2", "source_id": "p1", "text": "loss decreased"},
            ],
        }
        r1 = tool.call(payload)
        r2 = tool.call(payload)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Context Tool Tests
# ---------------------------------------------------------------------------

class TestContextTool:
    """Tests for Context extraction MCP tool wrapper."""

    def _make_tool(self):
        from services.context.tool import ContextTool
        return ContextTool()

    def test_manifest_valid(self):
        tool = self._make_tool()
        m = tool.manifest()
        assert m.name == "context"
        assert m.deterministic is True
        assert "chunks" in m.input_schema["required"]

    def test_extract_context_from_chunks(self):
        tool = self._make_tool()
        result = tool.call({
            "chunks": [
                {
                    "chunk_id": "c1",
                    "source_id": "paper_001",
                    "text": "We evaluate on the GLUE benchmark achieving 89.2% accuracy.",
                    "page": 3,
                    "context_id": "ctx_unknown",
                    "text_hash": "abc",
                    "start_char": 0,
                    "end_char": 60,
                    "metric_names": ["accuracy"],
                    "numeric_strings": ["89.2"],
                    "unit_strings": [],
                },
            ],
        })
        assert result["contexts_created"] >= 1
        assert len(result["chunks"]) == 1
        # Should have discovered GLUE context
        ctx_ids = [c["context_id"] for c in result["contexts"]]
        assert any("glue" in cid for cid in ctx_ids)

    def test_empty_chunks(self):
        tool = self._make_tool()
        result = tool.call({"chunks": []})
        assert result["contexts_created"] == 0
        assert result["chunks"] == []
        assert len(result["warnings"]) > 0

    def test_unknown_context_assigned(self):
        tool = self._make_tool()
        result = tool.call({
            "chunks": [
                {
                    "chunk_id": "c1",
                    "source_id": "paper_001",
                    "text": "This is a general statement with no dataset or metrics.",
                    "context_id": "ctx_unknown",
                    "text_hash": "def",
                    "start_char": 0,
                    "end_char": 50,
                },
            ],
        })
        assert result["unknown_chunks"] >= 1

    def test_deterministic_output(self):
        tool = self._make_tool()
        payload = {
            "chunks": [
                {
                    "chunk_id": "c1",
                    "source_id": "p1",
                    "text": "SQuAD F1-score of 92.1",
                    "context_id": "ctx_unknown",
                    "text_hash": "x",
                    "start_char": 0,
                    "end_char": 22,
                    "metric_names": ["f1-score"],
                    "numeric_strings": ["92.1"],
                    "unit_strings": [],
                },
            ],
        }
        r1 = tool.call(payload)
        r2 = tool.call(payload)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Proposal Tool Tests
# ---------------------------------------------------------------------------

class TestProposalTool:
    """Tests for Proposal generation MCP tool wrapper."""

    def _make_tool(self):
        from services.proposal.tool import ProposalTool
        return ProposalTool()

    def test_manifest_valid(self):
        tool = self._make_tool()
        m = tool.manifest()
        assert m.name == "proposal"
        assert m.deterministic is True
        assert "hypothesis_id" in m.input_schema["required"]
        assert "statement" in m.input_schema["required"]

    def test_generate_minimal_proposal(self):
        tool = self._make_tool()
        result = tool.call({
            "hypothesis_id": "hyp_001",
            "statement": "Transformer models generalize better than RNNs on low-resource tasks.",
        })
        assert result["proposal_id"].startswith("proposal_")
        assert result["hypothesis_id"] == "hyp_001"
        assert len(result["sections"]) == 5
        assert "full_markdown" in result
        assert "# Research Proposal" in result["full_markdown"]
        # Should warn about missing claims and references
        assert len(result["warnings"]) >= 1

    def test_generate_full_proposal(self):
        tool = self._make_tool()
        result = tool.call({
            "hypothesis_id": "hyp_002",
            "statement": "Fine-tuning BERT improves NER accuracy on CoNLL.",
            "rationale": "Pre-trained language models capture contextual features.",
            "assumptions": ["Pre-training data is representative", "CoNLL labels are reliable"],
            "supporting_claims": [
                {
                    "claim_id": "claim_01",
                    "subject": "BERT",
                    "predicate": "achieves",
                    "object_raw": "93.5% F1",
                    "metric_canonical": "F1",
                    "context_id": "ctx_conll",
                    "paper_id": "paper_001",
                },
            ],
            "known_risks": ["Domain shift between pre-training and task data"],
            "critiques": [
                {
                    "weak_assumptions": ["CoNLL may not represent modern entity distributions"],
                    "suggested_revisions": ["Include a more recent NER dataset for validation"],
                },
            ],
            "paper_references": [
                {
                    "paper_id": "paper_001",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "authors": ["Devlin", "Chang", "Lee", "Toutanova"],
                    "doi": "10.18653/v1/N19-1423",
                },
            ],
        })
        assert result["proposal_id"].startswith("proposal_")
        assert len(result["sections"]) == 5
        sections = {s["section"]: s for s in result["sections"]}
        assert "novelty" in sections
        assert "motivation" in sections
        assert "methodology" in sections
        assert "expected_outcomes" in sections
        assert "references" in sections
        # Check citations propagated
        assert "paper_001" in sections["novelty"]["citations_used"]
        # Check references
        assert len(result["references"]) == 1
        assert result["references"][0]["paper_id"] == "paper_001"

    def test_missing_hypothesis_id_raises(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="hypothesis_id is required"):
            tool.call({"statement": "test"})

    def test_missing_statement_raises(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="statement is required"):
            tool.call({"hypothesis_id": "hyp_001"})

    def test_deterministic_output(self):
        tool = self._make_tool()
        payload = {
            "hypothesis_id": "hyp_003",
            "statement": "Attention is all you need for sequence transduction.",
        }
        r1 = tool.call(payload)
        r2 = tool.call(payload)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Multimodal Tool Tests
# ---------------------------------------------------------------------------

class TestMultimodalTool:
    """Tests for Multimodal extraction MCP tool wrapper."""

    def _make_tool(self):
        from services.multimodal.tool import MultimodalTool
        return MultimodalTool()

    def test_manifest_valid(self):
        tool = self._make_tool()
        m = tool.manifest()
        assert m.name == "multimodal"
        assert m.deterministic is True
        assert "paper_id" in m.input_schema["required"]
        # chunks is now optional (pdf_path can be used instead)
        assert "chunks" in m.input_schema["properties"] or "pdf_path" in m.input_schema["properties"]

    def test_extract_table(self):
        tool = self._make_tool()
        result = tool.call({
            "paper_id": "paper_001",
            "chunks": [
                {
                    "chunk_id": "c1",
                    "text": "Model | Accuracy | F1\nBERT | 93.5 | 92.1\nGPT | 91.0 | 89.5",
                    "page": 4,
                },
            ],
        })
        assert result["paper_id"] == "paper_001"
        tables = [r for r in result["results"] if r["artifact_type"] == "table"]
        assert len(tables) >= 1
        # Check normalized data
        table = tables[0]
        assert "headers" in table["normalized_data"]
        assert table["normalized_data"]["row_count"] >= 2

    def test_extract_metrics(self):
        tool = self._make_tool()
        result = tool.call({
            "paper_id": "paper_002",
            "chunks": [
                {
                    "chunk_id": "c1",
                    "text": "Our model achieves accuracy = 95.3% and BLEU = 32.1 on the test set.",
                    "page": 5,
                },
            ],
        })
        metrics = [r for r in result["results"] if r["artifact_type"] == "metric"]
        assert len(metrics) >= 2
        metric_names = {m["normalized_data"]["metric"] for m in metrics}
        assert "accuracy" in metric_names
        assert "bleu" in metric_names

    def test_extract_caption(self):
        tool = self._make_tool()
        result = tool.call({
            "paper_id": "paper_003",
            "chunks": [
                {
                    "chunk_id": "c1",
                    "text": "Table 1: Results on GLUE benchmark across models.",
                    "page": 3,
                },
            ],
        })
        captions = [r for r in result["results"] if r.get("caption")]
        assert len(captions) >= 1

    def test_empty_chunks(self):
        tool = self._make_tool()
        result = tool.call({
            "paper_id": "paper_004",
            "chunks": [],
        })
        assert result["results"] == []
        assert result["extraction_count"] == 0
        assert len(result["warnings"]) > 0

    def test_page_constraint(self):
        tool = self._make_tool()
        result = tool.call({
            "paper_id": "paper_005",
            "chunks": [
                {"chunk_id": "c1", "text": "accuracy = 90%", "page": 1},
                {"chunk_id": "c2", "text": "accuracy = 95%", "page": 2},
            ],
            "page_constraint": 2,
        })
        for r in result["results"]:
            assert r["page_number"] == 2

    def test_missing_paper_id_raises(self):
        tool = self._make_tool()
        with pytest.raises(ValueError, match="paper_id is required"):
            tool.call({"chunks": []})

    def test_deterministic_output(self):
        tool = self._make_tool()
        payload = {
            "paper_id": "paper_006",
            "chunks": [
                {"chunk_id": "c1", "text": "precision = 88.7% and recall = 91.2%", "page": 1},
            ],
        }
        r1 = tool.call(payload)
        r2 = tool.call(payload)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Proposal Service Tests (non-tool, direct service)
# ---------------------------------------------------------------------------

class TestProposalService:
    """Tests for Proposal service business logic."""

    def _make_service(self):
        from services.proposal.service import ProposalService
        return ProposalService()

    def test_generate_produces_all_sections(self):
        from services.proposal.schemas import ProposalRequest
        svc = self._make_service()
        req = ProposalRequest(
            hypothesis_id="hyp_test",
            statement="Test hypothesis statement.",
        )
        result = svc.generate(req)
        assert result.proposal_id.startswith("proposal_")
        section_types = [s.section.value for s in result.sections]
        assert "novelty" in section_types
        assert "motivation" in section_types
        assert "methodology" in section_types
        assert "expected_outcomes" in section_types
        assert "references" in section_types

    def test_empty_hypothesis_raises(self):
        from services.proposal.schemas import ProposalRequest
        svc = self._make_service()
        with pytest.raises(ValueError):
            svc.generate(ProposalRequest(hypothesis_id="", statement="test"))

    def test_empty_statement_raises(self):
        from services.proposal.schemas import ProposalRequest
        svc = self._make_service()
        with pytest.raises(ValueError):
            svc.generate(ProposalRequest(hypothesis_id="hyp_1", statement=""))

    def test_markdown_output_contains_sections(self):
        from services.proposal.schemas import ProposalRequest
        svc = self._make_service()
        req = ProposalRequest(
            hypothesis_id="hyp_md",
            statement="Markdown generation test.",
            rationale="Testing that markdown assembly works.",
        )
        result = svc.generate(req)
        assert "## Novelty Statement" in result.full_markdown
        assert "## Motivation" in result.full_markdown
        assert "## Methodology Outline" in result.full_markdown
        assert "## Expected Outcomes" in result.full_markdown
        assert "## References" in result.full_markdown

    def test_references_deduplication(self):
        from services.proposal.schemas import ProposalRequest
        svc = self._make_service()
        req = ProposalRequest(
            hypothesis_id="hyp_dup",
            statement="Dedup test.",
            paper_references=[
                {"paper_id": "p1", "title": "Paper 1", "authors": ["A"]},
                {"paper_id": "p1", "title": "Paper 1", "authors": ["A"]},
                {"paper_id": "p2", "title": "Paper 2", "authors": ["B"]},
            ],
        )
        result = svc.generate(req)
        paper_ids = [r["paper_id"] for r in result.references]
        assert paper_ids == ["p1", "p2"]


# ---------------------------------------------------------------------------
# Multimodal Service Tests (non-tool, direct service)
# ---------------------------------------------------------------------------

class TestMultimodalService:
    """Tests for Multimodal extraction service business logic."""

    def _make_service(self):
        from services.multimodal.service import MultimodalExtractionService
        return MultimodalExtractionService()

    def test_extract_no_chunks(self):
        svc = self._make_service()
        results = svc.extract("paper_001", [])
        assert results == []

    def test_extract_missing_paper_id(self):
        svc = self._make_service()
        with pytest.raises(ValueError, match="paper_id is required"):
            svc.extract("", [{"text": "test"}])

    def test_extract_metric_normalization(self):
        svc = self._make_service()
        results = svc.extract("paper_001", [
            {"text": "accuracy = 95.3%", "page": 1, "chunk_id": "c1"},
        ])
        metrics = [r for r in results if r["artifact_type"] == "metric"]
        assert len(metrics) == 1
        assert metrics[0]["normalized_data"]["value_normalized"] == 95.3
        assert metrics[0]["normalized_data"]["is_percentage"] is True

    def test_extract_figure_caption(self):
        svc = self._make_service()
        results = svc.extract("paper_001", [
            {"text": "Figure 3: Architecture diagram of the proposed model.", "page": 2},
        ])
        figures = [r for r in results if r["artifact_type"] == "figure"]
        assert len(figures) == 1
        assert figures[0]["caption"] is not None


# ---------------------------------------------------------------------------
# Full Registry & Pipeline Tests
# ---------------------------------------------------------------------------

class TestMCPRegistryFull:
    """Tests for full registry with all 9 Phase 2 tools."""

    def _make_registry(self):
        from services.rag.tool import RAGTool
        from services.context.tool import ContextTool
        from services.proposal.tool import ProposalTool
        from services.multimodal.tool import MultimodalTool
        from services.ingestion.tool import IngestionTool
        from services.extraction.tool import ExtractionTool
        from services.normalization.tool import NormalizationTool
        from services.contradiction.tool import ContradictionTool
        from services.belief.tool import BeliefTool

        registry = MCPRegistry()
        for ToolCls in [
            IngestionTool, RAGTool, ContextTool, ExtractionTool,
            NormalizationTool, ContradictionTool, BeliefTool,
            MultimodalTool, ProposalTool,
        ]:
            registry.register(ToolCls())
        return registry

    def test_all_nine_tools_registered(self):
        registry = self._make_registry()
        names = registry.list_names()
        assert len(names) == 9
        expected = {
            "ingestion", "rag", "context", "extraction", "normalization",
            "contradiction", "belief", "multimodal", "proposal",
        }
        assert set(names) == expected

    def test_no_duplicate_names(self):
        registry = self._make_registry()
        names = registry.list_names()
        assert len(names) == len(set(names))

    def test_all_manifests_valid(self):
        registry = self._make_registry()
        for manifest in registry.list_manifests():
            assert manifest.name
            assert manifest.version
            assert manifest.description
            assert manifest.input_schema
            assert manifest.output_schema

    def test_core_pipeline_validates(self):
        registry = self._make_registry()
        pipeline = ["ingestion", "context", "extraction", "normalization", "contradiction", "belief"]
        registry.validate_pipeline(pipeline)  # Should not raise

    def test_full_pipeline_validates(self):
        registry = self._make_registry()
        pipeline = [
            "ingestion", "rag", "context", "extraction",
            "normalization", "contradiction", "belief",
            "multimodal", "proposal",
        ]
        registry.validate_pipeline(pipeline)  # Should not raise

    def test_invalid_pipeline_raises(self):
        from core.mcp import ToolNotFoundError
        registry = self._make_registry()
        with pytest.raises(ToolNotFoundError):
            registry.validate_pipeline(["ingestion", "nonexistent_tool"])

    def test_empty_pipeline_raises(self):
        registry = self._make_registry()
        with pytest.raises(ValueError):
            registry.validate_pipeline([])


# ---------------------------------------------------------------------------
# MCP Tool Contract Enforcement (All New Tools)
# ---------------------------------------------------------------------------

class TestToolContracts:
    """Verify all new tools conform to MCP contract."""

    @pytest.fixture(params=[
        "services.rag.tool.RAGTool",
        "services.context.tool.ContextTool",
        "services.proposal.tool.ProposalTool",
        "services.multimodal.tool.MultimodalTool",
    ])
    def tool_instance(self, request):
        module_path, class_name = request.param.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()

    def test_inherits_mcp_tool(self, tool_instance):
        from core.mcp.mcp_tool import MCPTool
        assert isinstance(tool_instance, MCPTool)

    def test_manifest_returns_mcp_manifest(self, tool_instance):
        from core.mcp.mcp_manifest import MCPManifest
        m = tool_instance.manifest()
        assert isinstance(m, MCPManifest)

    def test_manifest_name_format(self, tool_instance):
        m = tool_instance.manifest()
        assert m.name.isidentifier() or all(c.isalnum() or c == "_" for c in m.name)

    def test_manifest_has_required_fields(self, tool_instance):
        m = tool_instance.manifest()
        assert m.input_schema.get("required"), f"{m.name} input_schema has no required fields"
