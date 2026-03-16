"""Schemas for deterministic claim normalization (Step 3B)."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

from core.schemas.claim import Claim
from core.schemas.normalized_claim import NormalizedClaim, NoNormalization, NoNormalizationReason


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
