"""Tests for Phase 6: Evaluation framework and observability."""

from __future__ import annotations

import pytest


class TestAnnotationSchema:
    """Tests for ground truth annotation schema."""

    def test_load_ground_truth_jsonl(self):
        from evaluation.annotation_schema import GroundTruth

        gt = GroundTruth.from_jsonl("evaluation/ground_truth/annotated_5papers.jsonl")
        assert len(gt.papers) == 5
        assert len(gt.get_all_claims()) >= 5

    def test_get_claims_for_paper(self):
        from evaluation.annotation_schema import GroundTruth

        gt = GroundTruth.from_jsonl("evaluation/ground_truth/annotated_5papers.jsonl")
        claims = gt.get_claims_for_paper("real_paper_arxiv")
        assert len(claims) >= 1
        assert all(c.paper_id == "real_paper_arxiv" for c in claims)

    def test_ground_truth_save_load_roundtrip(self, tmp_path):
        from evaluation.annotation_schema import GroundTruth, PaperAnnotation, AnnotatedClaim

        gt = GroundTruth(papers=[
            PaperAnnotation(
                paper_id="paper_test",
                claims=[
                    AnnotatedClaim(
                        claim_id="c001",
                        paper_id="paper_test",
                        text="Test claim",
                        is_valid=True,
                    )
                ],
            )
        ])
        path = str(tmp_path / "test.jsonl")
        gt.to_jsonl(path)
        loaded = GroundTruth.from_jsonl(path)
        assert len(loaded.papers) == 1
        assert loaded.papers[0].claims[0].text == "Test claim"


class TestClaimMetrics:
    """Tests for claim extraction metrics."""

    def test_perfect_match(self):
        from evaluation.metrics import compute_claim_metrics

        claims = [{"text": "model achieves state of the art results"}]
        gold = [{"text": "model achieves state of the art results"}]
        m = compute_claim_metrics(claims, gold)
        assert m["f1"] == 1.0
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0

    def test_no_matches(self):
        from evaluation.metrics import compute_claim_metrics

        claims = [{"text": "completely unrelated text"}]
        gold = [{"text": "different topic entirely different words"}]
        m = compute_claim_metrics(claims, gold)
        assert m["f1"] == 0.0

    def test_empty_gold(self):
        from evaluation.metrics import compute_claim_metrics

        m = compute_claim_metrics([{"text": "a"}], [])
        assert m["recall"] == 0.0

    def test_partial_match(self):
        from evaluation.metrics import compute_claim_metrics

        claims = [{"text": "method achieves high accuracy"}, {"text": "unrelated thing"}]
        gold = [{"text": "method achieves high accuracy"}]
        m = compute_claim_metrics(claims, gold)
        assert 0.0 < m["f1"] <= 1.0


class TestClusterMetrics:
    """Tests for cluster quality metrics."""

    def test_perfect_clustering(self):
        from evaluation.metrics import compute_cluster_purity

        pred = [{"cluster_id": "c1", "paper_ids": ["p1", "p2"]}, {"cluster_id": "c2", "paper_ids": ["p3"]}]
        gold = [{"cluster_id": "g1", "paper_ids": ["p1", "p2"]}, {"cluster_id": "g2", "paper_ids": ["p3"]}]
        m = compute_cluster_purity(pred, gold)
        assert m["purity"] == 1.0
        assert m["n_papers"] == 3

    def test_empty_clusters(self):
        from evaluation.metrics import compute_cluster_purity

        m = compute_cluster_purity([], [])
        assert m["purity"] == 0.0

    def test_no_common_papers(self):
        from evaluation.metrics import compute_cluster_purity

        pred = [{"cluster_id": "c1", "paper_ids": ["p1"]}]
        gold = [{"cluster_id": "g1", "paper_ids": ["p2"]}]
        m = compute_cluster_purity(pred, gold)
        assert m["n_papers"] == 0


class TestHypothesisScoring:
    """Tests for hypothesis quality scoring."""

    def test_complete_hypothesis_scores_high(self):
        from evaluation.metrics import score_hypothesis

        hyp = {
            "statement": "Test hypothesis",
            "assumptions": ["assumption 1"],
            "independent_variables": ["var A"],
            "dependent_variables": ["var B"],
            "novelty_basis": "Novel because X",
            "confidence_score": 0.8,
            "grounding_claim_ids": ["c1", "c2", "c3", "c4", "c5"],
            "revision_history": [{"iteration": 1, "changes": "revised", "rationale": "because"}] * 3,
        }
        scores = score_hypothesis(hyp)
        assert scores["completeness"] == 1.0
        assert scores["aggregate"] > 0.5

    def test_minimal_hypothesis_scores_low(self):
        from evaluation.metrics import score_hypothesis

        hyp = {"statement": "minimal"}
        scores = score_hypothesis(hyp)
        assert scores["completeness"] < 0.5


class TestMetricsCollector:
    """Tests for runtime metrics collection."""

    def test_record_and_retrieve(self):
        from core.observability.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        collector.record_tool_invocation("s1", "ingestion", 100.0, "success", "abc", "def")
        collector.record_tool_invocation("s1", "extraction", 50.0, "success", "def", "ghi")
        collector.record_claims("s1", 10)
        collector.record_chunks("s1", 20)

        summary = collector.get_session_summary("s1")
        assert summary["step_count"] == 2
        assert summary["claim_count"] == 10
        assert summary["chunk_count"] == 20
        assert summary["claim_yield"] == 0.5
        assert summary["total_duration_ms"] == 150.0

    def test_global_summary(self):
        from core.observability.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        collector.record_tool_invocation("s2", "ingestion", 80.0, "success")
        collector.record_tool_invocation("s2", "extraction", 30.0, "error")

        gs = collector.get_global_summary()
        assert gs["total_invocations"] == 2
        assert gs["error_rate"] == 0.5
        assert "ingestion" in gs["per_tool"]

    def test_from_trace_entries(self):
        from core.observability.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        entries = [
            {"tool": "ingestion", "duration_ms": 100.0, "status": "success", "input_hash": "a", "output_hash": "b"},
            {"tool": "extraction", "duration_ms": 50.0, "status": "success", "input_hash": "b", "output_hash": "c"},
        ]
        collector.from_trace_entries("s3", entries)
        summary = collector.get_session_summary("s3")
        assert summary["step_count"] == 2

    def test_missing_session(self):
        from core.observability.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        summary = collector.get_session_summary("nonexistent")
        assert summary["found"] is False


class TestProvenanceAuditor:
    """Tests for provenance auditor."""

    def test_valid_proposal_audit(self):
        from core.observability.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        proposal = {
            "proposal_id": "p1",
            "hypothesis_id": "h1",
            "references": [{"paper_id": "paper1"}, {"paper_id": "paper2"}],
            "sections": [{"citations_used": ["paper1"]}],
        }
        result = auditor.audit_proposal(proposal, {"paper_ids": ["paper1", "paper2"]})
        assert result["valid"] is True
        assert result["citation_coverage"] == 1.0
        assert len(result["errors"]) == 0

    def test_missing_hypothesis_id(self):
        from core.observability.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        proposal = {"proposal_id": "p1", "hypothesis_id": "", "references": [], "sections": []}
        result = auditor.audit_proposal(proposal, {})
        assert result["valid"] is False
        assert any("hypothesis_id" in e for e in result["errors"])

    def test_trace_audit_complete(self):
        from core.observability.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        entries = [
            {"sequence": 0, "tool": "ingestion", "status": "success", "input_hash": "a", "output_hash": "b"},
            {"sequence": 1, "tool": "extraction", "status": "success", "input_hash": "b", "output_hash": "c"},
        ]
        result = auditor.audit_trace(entries)
        assert result["valid"] is True
        assert result["hash_coverage"] == 1.0
        assert result["hashed_steps"] == 2

    def test_trace_audit_missing_hashes(self):
        from core.observability.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        entries = [
            {"sequence": 0, "tool": "ingestion", "status": "success", "input_hash": "", "output_hash": ""},
        ]
        result = auditor.audit_trace(entries)
        assert result["hash_coverage"] == 0.0
        assert len(result["warnings"]) > 0

    def test_full_audit(self):
        from core.observability.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        result = auditor.full_audit(
            proposal={
                "proposal_id": "p1",
                "hypothesis_id": "h1",
                "references": [{"paper_id": "p1"}],
                "sections": [],
            },
            hypothesis={
                "hypothesis_id": "h1",
                "statement": "Test",
                "assumptions": ["a1"],
                "grounding_claim_ids": ["c1"],
            },
            trace_entries=[
                {"sequence": 0, "tool": "ingestion", "status": "success", "input_hash": "a", "output_hash": "b"}
            ],
            context={"paper_ids": ["p1"], "claim_ids": ["c1"]},
        )
        assert "proposal" in result
        assert "hypothesis" in result
        assert "trace" in result
        assert result["overall_valid"] is True


class TestCLICommands:
    """Tests for CLI command parsing."""

    def test_build_parser(self):
        from cli.app import build_parser

        parser = build_parser()
        args = parser.parse_args(["ingest", "test.pdf"])
        assert args.command == "ingest"
        assert args.pdf == "test.pdf"

    def test_analyze_command_parsing(self):
        from cli.app import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze", "paper.pdf", "--pause-at", "hypothesis_critique_loop"])
        assert args.command == "analyze"
        assert args.pause_at == "hypothesis_critique_loop"

    def test_status_command(self):
        from cli.app import main

        rc = main(["status"])
        assert rc == 0
