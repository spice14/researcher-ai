"""Phase 5 observability and evaluation tooling.

Implements structured logging, determinism verification,
evaluation metrics, and provenance audits.
"""

from core.observability.phase5 import (
    StructuredLogEvent,
    EvaluationAggregate,
    EvaluationInput,
    DeterminismSummary,
    DeterminismIssue,
    ProvenanceAuditResult,
    ProvenanceFinding,
    build_structured_log_event,
    verify_determinism_by_document,
    compare_schema_shapes,
    compute_evaluation_metrics,
    audit_provenance_assertions,
    structured_logs_from_execution_trace,
)

__all__ = [
    "StructuredLogEvent",
    "EvaluationAggregate",
    "EvaluationInput",
    "DeterminismSummary",
    "DeterminismIssue",
    "ProvenanceAuditResult",
    "ProvenanceFinding",
    "build_structured_log_event",
    "verify_determinism_by_document",
    "compare_schema_shapes",
    "compute_evaluation_metrics",
    "audit_provenance_assertions",
    "structured_logs_from_execution_trace",
]
