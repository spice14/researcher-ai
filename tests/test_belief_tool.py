"""Unit tests for BeliefTool (MCP wrapper).

Tests the tool interface, not the underlying service logic.
Focuses on empty-safe behavior required by Phase B.
"""

import pytest
from services.belief.tool import BeliefTool


class TestBeliefToolEmptySafe:
    """Test that BeliefTool handles empty inputs gracefully."""
    
    def test_belief_tool_handles_empty_normalized_claims(self):
        """PHASE B REQUIREMENT: BeliefTool must not crash on empty input.
        
        Before Phase B: raises ValueError("normalized_claims cannot be empty")
        After Phase B: returns empty belief state with zero counts
        """
        tool = BeliefTool()
        
        # Act
        result = tool.call({"normalized_claims": []})
        
        # Assert
        assert "belief_states" in result
        assert "supporting_count" in result
        assert "refuting_count" in result
        assert result["belief_states"] == []
        assert result["supporting_count"] == 0
        assert result["refuting_count"] == 0
    
    def test_belief_tool_handles_missing_normalized_claims_key(self):
        """BeliefTool should handle missing key with default empty list."""
        tool = BeliefTool()
        
        # Act
        result = tool.call({})  # No normalized_claims key
        
        # Assert
        assert result["belief_states"] == []
        assert result["supporting_count"] == 0
        assert result["refuting_count"] == 0
    
    def test_belief_tool_manifest_deterministic(self):
        """BeliefTool must declare itself as deterministic."""
        tool = BeliefTool()
        manifest = tool.manifest()
        
        assert manifest.deterministic is True
        assert manifest.name == "belief"
    
    def test_belief_tool_accepts_valid_normalized_claims(self):
        """BeliefTool should still work with valid claims (regression test)."""
        tool = BeliefTool()
        
        # Valid minimal claim
        valid_claim = {
            "claim_id": "test-001",
            "subject": "BERT",
            "predicate": "achieves",
            "object_raw": "93.2% accuracy",
            "metric_canonical": "ACCURACY",
            "value_raw": "93.2",
            "value_normalized": 93.2,
            "unit_normalized": "percent",
            "polarity": "NEUTRAL",
            "context_id": "test-context",
            "claim_subtype": "ABSOLUTE"
        }
        
        # Act
        result = tool.call({"normalized_claims": [valid_claim]})
        
        # Assert - should return belief state structure
        assert "belief_state" in result or "belief_states" in result
        # Don't assert specific values - service logic may vary


class TestBeliefToolInterface:
    """Test BeliefTool conforms to MCP interface requirements."""
    
    def test_manifest_has_required_fields(self):
        """Manifest must include name, version, schemas."""
        tool = BeliefTool()
        manifest = tool.manifest()
        
        assert manifest.name
        assert manifest.version
        assert manifest.input_schema
        assert manifest.output_schema
        assert "properties" in manifest.input_schema
        assert "normalized_claims" in manifest.input_schema["properties"]
    
    def test_call_returns_dict(self):
        """call() must return Dict[str, Any]."""
        tool = BeliefTool()
        result = tool.call({"normalized_claims": []})
        
        assert isinstance(result, dict)
    
    def test_deterministic_flag_exposed(self):
        """Manifest must expose deterministic=True."""
        tool = BeliefTool()
        assert tool.manifest().deterministic is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
