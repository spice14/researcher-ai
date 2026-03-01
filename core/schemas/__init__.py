"""
Core schemas for Researcher-AI.

This module defines the structured backbone of the system,
providing Pydantic models for:
- Evidence records
- Claims
- Hypotheses
- Experimental Contexts (Layer-0 architecture)

All intermediate reasoning operates over these typed representations.
Unstructured text is permitted only at ingestion and artifact generation boundaries.
"""

from core.schemas.evidence import EvidenceRecord, EvidenceContext, EvidenceProvenance
from core.schemas.claim import Claim, ClaimEvidence, ClaimConditions, Polarity, ConfidenceLevel
from core.schemas.normalized_claim import NormalizedClaim, NoNormalization, NoNormalizationReason
from core.schemas.hypothesis import Hypothesis, HypothesisRevision
from core.schemas.experimental_context import (
    ExperimentalContext,
    ContextRegistry,
    MetricDefinition,
    EvaluationProtocol,
    TaskType,
)

__all__ = [
    "EvidenceRecord",
    "EvidenceContext",
    "EvidenceProvenance",
    "Claim",
    "ClaimEvidence",
    "ClaimConditions",
    "NormalizedClaim",
    "NoNormalization",
    "NoNormalizationReason",
    "Hypothesis",
    "HypothesisRevision",
    "ConfidenceLevel",
    "Polarity",
    "ExperimentalContext",
    "ContextRegistry",
    "MetricDefinition",
    "EvaluationProtocol",
    "TaskType",
]
