"""Schemas for deterministic claim normalization (Step 3B)."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

from core.schemas.claim import Claim, ClaimSubtype, Polarity


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
    """Normalized claim representation with canonicalized values."""

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


class NormalizationRequest(BaseModel):
    """Input schema for normalization."""

    claim: Claim = Field(..., description="Claim to normalize")


class NormalizationResult(BaseModel):
    """Output schema for normalization."""

    normalized: Optional[NormalizedClaim] = Field(None, description="Normalized claim")
    no_normalization: Optional[NoNormalization] = Field(None, description="Reason for no normalization")
    
    # Diagnostic tracking (debug mode only)
    diagnostic: Optional[dict] = Field(None, description="Diagnostic info if debug_mode=True")

    @model_validator(mode="after")
    def validate_xor(self) -> "NormalizationResult":
        if bool(self.normalized) == bool(self.no_normalization):
            raise ValueError("Exactly one of normalized or no_normalization must be provided")
        return self
