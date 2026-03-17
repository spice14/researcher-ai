"""
Validators for ScholarOS schemas.

Provides validation logic beyond Pydantic's built-in capabilities:
- Cross-schema validation
- Business logic enforcement
- Consistency checking
- Provenance verification

All validators return structured validation results for observability.
"""

from core.validators.schema_validator import (
    SchemaValidator,
    ValidationResult,
    ValidationError,
)
from core.validators.paper_validator import PaperValidator
from core.validators.chunk_validator import ChunkValidator
from core.validators.claim_validator import ClaimValidator
from core.validators.experimental_context_validator import ExperimentalContextValidator
from core.validators.hypothesis_validator import HypothesisValidator
from core.validators.evidence_validator import EvidenceValidator
from core.validators.normalized_claim_validator import NormalizedClaimValidator
from core.validators.cluster_map_validator import ClusterMapValidator
from core.validators.contradiction_report_validator import ContradictionReportValidator
from core.validators.critique_validator import CritiqueValidator
from core.validators.proposal_validator import ProposalValidator
from core.validators.extraction_result_validator import ExtractionResultValidator
from core.validators.session_validator import SessionValidator

__all__ = [
    "SchemaValidator",
    "ValidationResult",
    "ValidationError",
    "PaperValidator",
    "ChunkValidator",
    "ClaimValidator",
    "ExperimentalContextValidator",
    "HypothesisValidator",
    "EvidenceValidator",
    "NormalizedClaimValidator",
    "ClusterMapValidator",
    "ContradictionReportValidator",
    "CritiqueValidator",
    "ProposalValidator",
    "ExtractionResultValidator",
    "SessionValidator",
]
