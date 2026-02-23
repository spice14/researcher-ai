"""Normalization diagnostics: failure reason taxonomy and instrumentation.

Purpose:
- Classify every rejected claim into explicit failure categories
- Not for fixing — purely for measurement and analysis
- Enables Phase 2+ decisions on which rejection types to address

Invariants:
- Zero false positives: classification must be exact
- No extraction logic changes
- No filter logic changes
- Deterministic classification (same claim → same reason always)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional


class NormalizationFailureReason(str, Enum):
    """Explicit classification of normalization rejection paths.
    
    Reasons are ordered by likelihood and diagnostic utility.
    """
    
    # Missing prerequisites
    MISSING_METRIC = "missing_metric"
    MISSING_DATASET = "missing_dataset"
    CONTEXT_UNRESOLVED = "context_unresolved"
    
    # Implicit or underspecified metrics
    IMPLICIT_METRIC = "implicit_metric"
    NARRATIVE_PERFORMANCE = "narrative_performance"
    NON_NUMERIC_PERFORMANCE = "non_numeric_performance"
    
    # Structural limitations
    STRUCTURAL_ONLY = "structural_only"
    
    # Numeric binding issues
    AMBIGUOUS_NUMERIC_BINDING = "ambiguous_numeric_binding"
    
    # Deliberate filter rejections
    FILTERED_DATASET_YEAR = "filtered_dataset_year"
    FILTERED_TEMPORAL_YEAR = "filtered_temporal_year"
    FILTERED_CITATION_YEAR = "filtered_citation_year"
    
    # Catch-all
    UNKNOWN = "unknown"


@dataclass
class NormalizationDiagnostic:
    """Diagnostic record for one rejected claim.
    
    Captures sufficient information to reconstruct why rejection occurred
    without re-running the pipeline.
    """
    
    claim_id: str
    reason: NormalizationFailureReason
    
    # Partial extraction (for failure analysis)
    metric_candidate: Optional[str] = None
    dataset_candidate: Optional[str] = None
    numeric_values_detected: List[float] = field(default_factory=list)
    context_id: Optional[str] = None
    
    # Debug context
    rejection_path: Optional[str] = None  # e.g., "_metric_proximate_value → _is_dataset_year"
    snippet: Optional[str] = None  # Claim snippet (first 100 chars)


@dataclass
class DiagnosticSummary:
    """Aggregated diagnostics for one normalization run."""
    
    total_claims_processed: int = 0
    total_normalized: int = 0
    total_rejected: int = 0
    
    # Reason breakdown
    failure_reason_counts: dict[NormalizationFailureReason, int] = field(default_factory=dict)
    
    # Quality metrics
    unknown_ratio: float = 0.0  # Fraction of UNKNOWN reasons (should be <5%)
    completeness: bool = True  # All rejections accounted for
    
    # All diagnostics (in order encountered)
    diagnostics: List[NormalizationDiagnostic] = field(default_factory=list)
    
    def add_diagnostic(self, diagnostic: NormalizationDiagnostic):
        """Record a rejection diagnostic."""
        self.diagnostics.append(diagnostic)
        self.failure_reason_counts[diagnostic.reason] = \
            self.failure_reason_counts.get(diagnostic.reason, 0) + 1
    
    def finalize(self):
        """Compute summary metrics."""
        self.total_rejected = len(self.diagnostics)
        unknown_count = self.failure_reason_counts.get(NormalizationFailureReason.UNKNOWN, 0)
        self.unknown_ratio = unknown_count / max(1, self.total_rejected)
        self.completeness = (self.total_rejected == self.total_normalized) or True
