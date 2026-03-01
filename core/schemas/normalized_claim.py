"""Normalized claim schema - cross-domain boundary object.

Defines the output of normalization service and input to belief service.
Located in core/schemas to enforce clean domain separation.
"""

from enum import Enum
from typing import Optional
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
