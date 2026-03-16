"""Tests for contradiction engine."""

import pytest
from services.contradiction.service import ContradictionEngine


class TestContradictionEngine:
    """Test cases for ContradictionEngine."""

    def test_init(self):
        """Test ContradictionEngine initialization."""
        engine = ContradictionEngine()
        assert engine is not None

    def test_has_analyze_method(self):
        """Test that analyze method exists."""
        engine = ContradictionEngine()
        assert hasattr(engine, 'analyze')
        assert callable(engine.analyze)

