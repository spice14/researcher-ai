"""Tests for Phase 5 observability and evaluation tooling."""

from datetime import datetime, timezone

from core.mcp.trace import ExecutionTrace, TraceEntry
from core.observability.phase5 import (
    EvaluationInput,
    audit_provenance_assertions,
    build_structured_log_event,
    compare_schema_shapes,
    compute_evaluation_metrics,
    structured_logs_from_execution_trace,
    verify_determinism_by_document,
)


def test_structured_log_event_has_required_phase5_fields():
    event = build_structured_log_event(
        trace_id="trace_001",
        service="ingestion",
        action="ingest_text",
        input_payload={"source_id": "paper_a", "raw_text": "hello"},
        output_payload={"chunks": [{"chunk_id": "c1"}]},
        latency_ms=12.5,
        model=None,
        prompt_version=None,
        token_usage={},
        error=None,
    )

    assert event.trace_id == "trace_001"
    assert event.service == "ingestion"
    assert event.action == "ingest_text"
    assert len(event.input_hash) == 64
    assert len(event.output_hash) == 64
    assert event.latency_ms == 12.5
    assert event.error is None


def test_determinism_summary_detects_nondeterministic_document():
    summary = verify_determinism_by_document(
        {
            "paper_a": [
                {"claims": 4, "chunks": 100},
                {"claims": 4, "chunks": 100},
            ],
            "paper_b": [
                {"claims": 7, "chunks": 120},
                {"claims": 8, "chunks": 120},
            ],
        }
    )

    assert summary.total_documents == 2
    assert summary.deterministic_documents == 1
    assert summary.determinism_rate == 0.5
    assert len(summary.issues) == 1


def test_compare_schema_shapes_ignores_value_content_but_checks_structure():
    left = {
        "hypotheses": [{"id": "h1", "score": 0.2}],
        "meta": {"iteration": 1, "done": False},
    }
    right = {
        "hypotheses": [{"id": "h9", "score": 0.9}],
        "meta": {"iteration": 7, "done": True},
    }
    different = {
        "hypotheses": [{"id": "h9", "score": "0.9"}],
        "meta": {"iteration": 7, "done": True},
    }

    assert compare_schema_shapes(left, right) is True
    assert compare_schema_shapes(left, different) is False


def test_compute_evaluation_metrics_matches_plan_formulae():
    rows = [
        EvaluationInput(
            paper_id="p1",
            expected_claims=10,
            extracted_claims=8,
            collapsed_claim_pairs=5,
            truly_equivalent_collapses=4,
            known_contradictions=6,
            contradictions_found=3,
            hypotheses_generated=2,
            hypotheses_grounded=1,
            proposals_generated=2,
            proposals_complete=1,
        ),
        EvaluationInput(
            paper_id="p2",
            expected_claims=5,
            extracted_claims=5,
            collapsed_claim_pairs=3,
            truly_equivalent_collapses=3,
            known_contradictions=4,
            contradictions_found=4,
            hypotheses_generated=3,
            hypotheses_grounded=3,
            proposals_generated=1,
            proposals_complete=1,
        ),
    ]

    metrics = compute_evaluation_metrics(rows)

    assert metrics.claim_extraction_yield == 13 / 15
    assert metrics.normalization_precision == 7 / 8
    assert metrics.contradiction_recall == 7 / 10
    assert metrics.hypothesis_grounding_rate == 4 / 5
    assert metrics.proposal_completeness == 2 / 3


def test_provenance_audit_enforces_contract_and_allows_low_ungrounded():
    audit = audit_provenance_assertions(
        [
            {
                "assertion_id": "a1",
                "paper_id": "paper_1",
                "chunk_id": "chunk_7",
            },
            {
                "assertion_id": "a2",
                "confidence": "LOW",
                "ungrounded": True,
            },
            {
                "assertion_id": "a3",
                "confidence": "medium",
                "ungrounded": False,
            },
        ]
    )

    assert audit.checked == 3
    assert audit.violations == 1
    assert audit.passed is False
    assert audit.findings[0].assertion_id == "a3"


def test_structured_logs_from_execution_trace_preserves_llm_metadata():
    now = datetime.now(timezone.utc)
    trace = ExecutionTrace(
        session_id="sess_1",
        started_at=now,
        completed_at=now,
        final_output_hash="abc123",
        final_output={"ok": True},
        pipeline_definition=["hypothesis"],
        entries=[
            TraceEntry(
                sequence=0,
                tool="hypothesis",
                input_hash="in_hash",
                output_hash="out_hash",
                timestamp=now,
                status="success",
                error_message=None,
                duration_ms=44.0,
                attempt=1,
                phase="hypothesis_generate",
                model_name="local-model",
                prompt_version="v1.2.0",
                token_usage={"prompt_tokens": 123, "completion_tokens": 45},
            )
        ],
    )

    events = structured_logs_from_execution_trace(trace)

    assert len(events) == 1
    assert events[0].trace_id == "sess_1"
    assert events[0].service == "hypothesis"
    assert events[0].action == "hypothesis_generate"
    assert events[0].model == "local-model"
    assert events[0].prompt_version == "v1.2.0"
    assert events[0].token_usage["prompt_tokens"] == 123
