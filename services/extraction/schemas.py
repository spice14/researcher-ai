"""Schemas for deterministic claim extraction."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from services.ingestion.schemas import IngestionChunk
from core.schemas.claim import Claim


class NoClaimReason(str, Enum):
    """Reasons for not extracting a claim from a sentence chunk."""

    CONTEXT_MISSING = "context_missing"
    HEDGED_STATEMENT = "hedged_statement"
    NO_NUMBER = "no_number"
    NO_METRIC = "no_metric"
    NO_PREDICATE = "no_predicate"
    NON_PERFORMANCE_NUMERIC = "non_performance_numeric"
    COMPOUND_METRIC = "compound_metric"
    SUBJECT_MISSING = "subject_missing"
    OBJECT_MISSING = "object_missing"
    NON_CLAIM = "non_claim"
    TABLE_FRAGMENT_REJECTED = "table_fragment_rejected"


class NoClaim(BaseModel):
    """Non-claim extraction result."""

    reason_code: NoClaimReason = Field(..., description="Why extraction was rejected")
    detail: Optional[str] = Field(None, description="Optional detail for debugging")


class ClaimExtractionRequest(BaseModel):
    """Input schema for claim extraction."""

    chunk: IngestionChunk = Field(..., description="Sentence-level chunk to analyze")


class ClaimExtractionResult(BaseModel):
    """Output schema for claim extraction."""

    claim: Optional[Claim] = Field(None, description="Extracted claim")
    no_claim: Optional[NoClaim] = Field(None, description="Reason for no extraction")

    @model_validator(mode="after")
    def validate_xor(self) -> "ClaimExtractionResult":
        if bool(self.claim) == bool(self.no_claim):
            raise ValueError("Exactly one of claim or no_claim must be provided")
        return self
