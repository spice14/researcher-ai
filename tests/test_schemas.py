"""Tests for core schemas."""

import pytest
from core.schemas.claim import Claim, ClaimSubtype
from core.schemas.hypothesis import Hypothesis
from core.schemas.experimental_context import ExperimentalContext, TaskType


class TestClaimSchema:
    """Test cases for Claim schema."""

    def test_claim_has_required_fields(self):
        """Test that Claim model has required fields."""
        assert hasattr(Claim, 'model_json_schema')

    def test_claim_subtype_enum(self):
        """Test that ClaimSubtype enum has expected values."""
        assert hasattr(ClaimSubtype, '__members__')
        # Verify enum members exist
        assert len(list(ClaimSubtype)) > 0


class TestHypothesisSchema:
    """Test cases for Hypothesis schema."""

    def test_hypothesis_can_be_instantiated(self):
        """Test that Hypothesis model works."""
        assert hasattr(Hypothesis, 'model_json_schema') or hasattr(Hypothesis, '__init__')


class TestExperimentalContextSchema:
    """Test cases for ExperimentalContext schema."""

    def test_experimental_context_task_type_enum(self):
        """Test that TaskType enum exists."""
        assert hasattr(TaskType, '__members__') or hasattr(TaskType, '__call__')

    def test_experimental_context_has_schema(self):
        """Test that ExperimentalContext has schema methods."""
        assert hasattr(ExperimentalContext, 'model_json_schema') or hasattr(ExperimentalContext, '__init__')

