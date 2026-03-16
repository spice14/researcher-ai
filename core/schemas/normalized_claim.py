"""Normalized claim schema - cross-domain boundary object.

Defines the output of normalization service and input to belief service.
Located in core/schemas to enforce clean domain separation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from core.schemas.claim import ClaimSubtype, Polarity


class NoNormalizationReason(str, Enum):
    """Reasons for not normalizing a claim."""

    MISSING_METRIC = "missing_metric"
    MISSING_VALUE = "missing_value"
    UNPARSEABLE_UNIT = "unparseable_unit"
    AMBIGUOUS_NUMERIC_BINDING = "ambiguous_numeric_binding"


class NoNormalization(BaseModel):
    """Non-normalization result."""

    reason_code: NoNormalizationReason = Field(..., description="Why normalization was rejected")
    detail: Optional[str] = Field(None, description="Optional detail for debugging")


class NormalizedClaim(BaseModel):
    """Normalized claim representation with canonicalized values.
    
    Output of normalization service.
    Input to belief and contradiction services.
    Centralized in core/schemas to prevent cross-service coupling.
    """

    claim_id: str = Field(..., description="Original claim identifier")
    normalized_claim_id: Optional[str] = Field(None, description="Stable identifier for normalized claim cluster")
    canonical_text: Optional[str] = Field(None, description="Canonical normalized claim text")
    source_claim_ids: List[str] = Field(default_factory=list, description="Source claim identifiers")
    domain: Optional[str] = Field(None, description="Claim domain")
    metric: Optional[str] = Field(None, description="Compatibility alias for metric_canonical")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Structured conditions for claim applicability")
    evidence_strength: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional evidence strength score",
    )
    context_id: Optional[str] = Field(None, description="Experimental context identifier")
    subject: str = Field(..., description="Claim subject")
    predicate: str = Field(..., description="Claim predicate")
    object_raw: str = Field(..., description="Original object string")
    metric_canonical: str = Field(..., description="Canonical metric name")
    value_raw: str = Field(..., description="Raw numeric value string")
    value_normalized: float = Field(..., description="Normalized numeric value")
    unit_normalized: Optional[str] = Field(None, description="Canonical unit")
    polarity: Polarity = Field(..., description="Claim polarity")
    claim_subtype: ClaimSubtype = Field(
        default=ClaimSubtype.ABSOLUTE,
        description="Value semantics: absolute measurement or delta improvement. "
                    "Delta claims must be excluded from value-range aggregation.",
    )
