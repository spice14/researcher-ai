"""Session schema for orchestrated workflows."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator


class Session(BaseModel):
    """Structured workflow session state."""

    session_id: str = Field(..., description="Session identifier", min_length=1)
    user_input: str = Field(..., description="Original user input or intent", min_length=1)
    active_paper_ids: List[str] = Field(default_factory=list, description="Active paper identifiers")
    hypothesis_ids: List[str] = Field(default_factory=list, description="Associated hypothesis identifiers")
    phase: str = Field(..., description="Current orchestrator phase", min_length=1)
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Session last update timestamp")

    @field_validator("session_id", "user_input", "phase")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Required text fields must be non-empty")
        return v

    @field_validator("active_paper_ids", "hypothesis_ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        for item in v:
            if len(item.strip()) == 0:
                raise ValueError("Identifiers must be non-empty strings")
        return v

    @model_validator(mode="after")
    def validate_temporal_order(self) -> "Session":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at")
        return self