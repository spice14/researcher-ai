"""Phase 5 observability and evaluation utilities.

This module implements the final-plan tooling requirements:
- structured logging records
- determinism verification across repeated runs
- evaluation metric aggregation
- provenance audit enforcement
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field

from core.mcp.trace import hash_payload
from core.mcp.trace import ExecutionTrace


class StructuredLogEvent(BaseModel):
    """Canonical structured log entry for services and agents."""

    trace_id: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    input_hash: str = Field(..., min_length=1)
    output_hash: str = Field(..., min_length=1)
    latency_ms: float = Field(..., ge=0)
    model: Optional[str] = Field(default=None)
    prompt_version: Optional[str] = Field(default=None)
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeterminismIssue(BaseModel):
    """A non-deterministic output finding for one document."""

    document_id: str
    expected_hash: str
    observed_hash: str
    run_index: int = Field(..., ge=1)


class DeterminismSummary(BaseModel):
    """Aggregated determinism status across documents."""

    total_documents: int = Field(..., ge=0)
    deterministic_documents: int = Field(..., ge=0)
    determinism_rate: float = Field(..., ge=0.0, le=1.0)
    issues: List[DeterminismIssue] = Field(default_factory=list)


class EvaluationInput(BaseModel):
    """Per-paper input row for Phase 5 evaluation metrics."""

    paper_id: str

    expected_claims: int = Field(0, ge=0)
    extracted_claims: int = Field(0, ge=0)

    collapsed_claim_pairs: int = Field(0, ge=0)
    truly_equivalent_collapses: int = Field(0, ge=0)

    known_contradictions: int = Field(0, ge=0)
    contradictions_found: int = Field(0, ge=0)

    hypotheses_generated: int = Field(0, ge=0)
    hypotheses_grounded: int = Field(0, ge=0)

    proposals_generated: int = Field(0, ge=0)
    proposals_complete: int = Field(0, ge=0)


class EvaluationAggregate(BaseModel):
    """Phase 5 aggregate metrics defined in the implementation plan."""

    claim_extraction_yield: float = Field(..., ge=0.0)
    normalization_precision: float = Field(..., ge=0.0)
    contradiction_recall: float = Field(..., ge=0.0)
    hypothesis_grounding_rate: float = Field(..., ge=0.0)
    proposal_completeness: float = Field(..., ge=0.0)


class ProvenanceFinding(BaseModel):
    """A provenance audit failure for one assertion payload."""

    assertion_id: str
    status: str
    reason: str


class ProvenanceAuditResult(BaseModel):
    """Outcome of provenance auditing over assertion payloads."""

    passed: bool
    checked: int = Field(..., ge=0)
    violations: int = Field(..., ge=0)
    findings: List[ProvenanceFinding] = Field(default_factory=list)


def build_structured_log_event(
    *,
    trace_id: str,
    service: str,
    action: str,
    input_payload: Mapping[str, Any],
    output_payload: Mapping[str, Any],
    latency_ms: float,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    token_usage: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> StructuredLogEvent:
    """Create a standard Phase 5 log event with deterministic hashes."""

    return StructuredLogEvent(
        trace_id=trace_id,
        service=service,
        action=action,
        input_hash=hash_payload(dict(input_payload)),
        output_hash=hash_payload(dict(output_payload)),
        latency_ms=latency_ms,
        model=model,
        prompt_version=prompt_version,
        token_usage=token_usage or {},
        error=error,
    )


def verify_determinism_by_document(
    document_runs: Mapping[str, Sequence[Mapping[str, Any]]],
) -> DeterminismSummary:
    """Verify deterministic outputs for repeated runs per document.

    For each document id, run #1 is treated as the baseline hash and all
    subsequent runs must match.
    """

    issues: List[DeterminismIssue] = []
    deterministic_docs = 0

    for document_id, runs in document_runs.items():
        if not runs:
            continue

        baseline_hash = hash_payload(dict(runs[0]))
        doc_deterministic = True

        for idx, run_output in enumerate(runs[1:], start=2):
            observed_hash = hash_payload(dict(run_output))
            if observed_hash != baseline_hash:
                doc_deterministic = False
                issues.append(
                    DeterminismIssue(
                        document_id=document_id,
                        expected_hash=baseline_hash,
                        observed_hash=observed_hash,
                        run_index=idx,
                    )
                )

        if doc_deterministic:
            deterministic_docs += 1

    total_docs = len(document_runs)
    rate = (deterministic_docs / total_docs) if total_docs else 1.0
    return DeterminismSummary(
        total_documents=total_docs,
        deterministic_documents=deterministic_docs,
        determinism_rate=rate,
        issues=issues,
    )


def _schema_shape(value: Any) -> Any:
    """Reduce arbitrary payloads to structure-only shapes."""

    if isinstance(value, dict):
        return {k: _schema_shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        # Preserve list cardinality and element shape order for strict structure checks.
        return [_schema_shape(v) for v in value]
    if value is None:
        return "null"
    return type(value).__name__


def compare_schema_shapes(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Return True when two outputs have identical structural schema shape."""

    return _schema_shape(dict(left)) == _schema_shape(dict(right))


def compute_evaluation_metrics(rows: Sequence[EvaluationInput]) -> EvaluationAggregate:
    """Compute Phase 5 evaluation metrics from aggregated per-paper rows."""

    expected_claims = sum(r.expected_claims for r in rows)
    extracted_claims = sum(r.extracted_claims for r in rows)

    collapsed_pairs = sum(r.collapsed_claim_pairs for r in rows)
    equivalent_collapses = sum(r.truly_equivalent_collapses for r in rows)

    known_contradictions = sum(r.known_contradictions for r in rows)
    contradictions_found = sum(r.contradictions_found for r in rows)

    hypotheses_generated = sum(r.hypotheses_generated for r in rows)
    hypotheses_grounded = sum(r.hypotheses_grounded for r in rows)

    proposals_generated = sum(r.proposals_generated for r in rows)
    proposals_complete = sum(r.proposals_complete for r in rows)

    def ratio(num: int, den: int) -> float:
        return float(num / den) if den > 0 else 0.0

    return EvaluationAggregate(
        claim_extraction_yield=ratio(extracted_claims, expected_claims),
        normalization_precision=ratio(equivalent_collapses, collapsed_pairs),
        contradiction_recall=ratio(contradictions_found, known_contradictions),
        hypothesis_grounding_rate=ratio(hypotheses_grounded, hypotheses_generated),
        proposal_completeness=ratio(proposals_complete, proposals_generated),
    )


def audit_provenance_assertions(assertions: Sequence[Mapping[str, Any]]) -> ProvenanceAuditResult:
    """Audit assertion-level provenance contract.

    Contract:
    - valid assertion must include both paper_id and chunk_id
    - OR must be explicitly marked as low-confidence and ungrounded
    """

    findings: List[ProvenanceFinding] = []

    for idx, item in enumerate(assertions):
        assertion_id = str(item.get("assertion_id") or item.get("id") or f"assertion_{idx + 1}")

        has_paper = bool(item.get("paper_id"))
        has_chunk = bool(item.get("chunk_id"))

        confidence = str(item.get("confidence", "")).strip().lower()
        ungrounded = bool(item.get("ungrounded", False))

        if has_paper and has_chunk:
            continue

        if confidence == "low" and ungrounded:
            continue

        findings.append(
            ProvenanceFinding(
                assertion_id=assertion_id,
                status="error",
                reason="Missing paper_id/chunk_id provenance and not marked low-confidence ungrounded",
            )
        )

    return ProvenanceAuditResult(
        passed=len(findings) == 0,
        checked=len(assertions),
        violations=len(findings),
        findings=findings,
    )


def structured_logs_from_execution_trace(trace: ExecutionTrace) -> List[StructuredLogEvent]:
    """Convert an orchestrator execution trace to Phase 5 structured log events."""

    events: List[StructuredLogEvent] = []
    for entry in trace.entries:
        events.append(
            StructuredLogEvent(
                trace_id=trace.session_id,
                service=entry.tool,
                action=entry.phase or entry.tool,
                input_hash=entry.input_hash,
                output_hash=entry.output_hash,
                latency_ms=entry.duration_ms,
                model=entry.model_name,
                prompt_version=entry.prompt_version,
                token_usage=entry.token_usage or {},
                error=entry.error_message,
                timestamp=entry.timestamp,
            )
        )
    return events
