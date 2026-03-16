"""Belief Service as MCP Tool — belief state construction.

Wraps belief.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.belief.service import BeliefEngine


class BeliefTool(MCPTool):
    """MCP wrapper for belief service."""
    
    def __init__(self):
        """Initialize with internal service instance."""
        self._service = BeliefEngine()
    
    def manifest(self) -> MCPManifest:
        """Define belief tool interface."""
        return MCPManifest(
            name="belief",
            version="1.0.0",
            description="Construct belief state from normalized claims",
            input_schema={
                "type": "object",
                "properties": {
                    "normalized_claims": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Normalized claims"
                    }
                },
                "required": ["normalized_claims"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "belief_state": {"type": "object"},
                    "warnings": {"type": "array"}
                },
                "required": ["belief_state"]
            },
            deterministic=True
        )
    
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute belief state construction with explicit payload."""
        from services.normalization.schemas import NormalizedClaim
        from core.schemas.claim import Polarity, ClaimSubtype
        from services.belief.schemas import BeliefRequest
        
        normalized_claims = payload.get("normalized_claims", [])
        if not normalized_claims:
            # Empty input → empty belief state (graceful degradation)
            return {
                "belief_states": [],
                "supporting_count": 0,
                "refuting_count": 0
            }
        
        # Build claim objects
        claim_objs = [self._build_normalized_claim(nc) for nc in normalized_claims]
        
        # Call service
        request = BeliefRequest(
            normalized_claims=claim_objs,
            contradictions=[]
        )
        
        belief_states = self._service.compute_beliefs(request)
        
        # Return first belief state or empty
        if not belief_states:
            return {"belief_states": [], "warnings": []}
        
        belief_state = belief_states[0]
        return self._format_belief_output(belief_state)
    
    def _build_normalized_claim(self, nc_dict: Dict[str, Any]):
        """Build a NormalizedClaim from dict."""
        from core.schemas.normalized_claim import NormalizedClaim
        from core.schemas.claim import Polarity, ClaimSubtype
        
        # Resolve enums
        polarity = self._resolve_enum(Polarity, nc_dict.get("polarity"), Polarity.NEUTRAL)
        subtype = self._resolve_enum(ClaimSubtype, nc_dict.get("claim_subtype"), ClaimSubtype.ABSOLUTE)
        
        return NormalizedClaim(
            claim_id=nc_dict.get("claim_id"),
            subject=nc_dict.get("subject"),
            predicate=nc_dict.get("predicate"),
            object_raw=nc_dict.get("object_raw", ""),
            metric_canonical=nc_dict.get("metric_canonical"),
            value_raw=nc_dict.get("value_raw", ""),
            value_normalized=float(nc_dict.get("value_normalized", 0.0)),
            unit_normalized=nc_dict.get("unit_normalized"),
            polarity=polarity,
            context_id=nc_dict.get("context_id"),
            claim_subtype=subtype
        )
    
    def _resolve_enum(self, enum_cls, value: Any, default: Any):
        """Resolve a value to its enum."""
        if isinstance(value, enum_cls):
            return value
        if not isinstance(value, str):
            return default
        try:
            for member in enum_cls.__members__.values():
                if member.value == value or member.name == value.upper():
                    return member
        except (AttributeError, TypeError):
            pass
        return default
    
    def _format_belief_output(self, belief_state) -> Dict[str, Any]:
        """Format belief state for output."""
        summary = belief_state.normalized_value_summary
        return {
            "belief_state": {
                "proposition_id": belief_state.proposition_id,
                "context_id": belief_state.context_id,
                "metric": belief_state.metric,
                "normalized_value_summary": {
                    "min": summary.min,
                    "max": summary.max,
                    "mean": summary.mean
                },
                "supporting_count": belief_state.supporting_count,
                "refuting_count": belief_state.refuting_count,
                "contradiction_density": belief_state.contradiction_density,
                "consensus_strength": belief_state.consensus_strength,
                "qualitative_confidence": belief_state.qualitative_confidence.value if hasattr(belief_state.qualitative_confidence, 'value') else str(belief_state.qualitative_confidence),
                "epistemic_status": belief_state.epistemic_status.value if hasattr(belief_state.epistemic_status, 'value') else str(belief_state.epistemic_status)
            },
            "warnings": []
        }
