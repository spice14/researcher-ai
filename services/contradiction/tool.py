"""Contradiction Service as MCP Tool — contradiction detection.

Wraps contradiction.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.contradiction.service import ContradictionEngine


class ContradictionTool(MCPTool):
    """MCP wrapper for contradiction service."""
    
    def __init__(self):
        """Initialize with internal service instance."""
        self._service = ContradictionEngine()
    
    def manifest(self) -> MCPManifest:
        """Define contradiction tool interface."""
        return MCPManifest(
            name="contradiction",
            version="1.0.0",
            description="Detect contradictions among claims in belief state",
            input_schema={
                "type": "object",
                "properties": {
                    "belief_state": {
                        "type": "object",
                        "description": "Belief state from previous step"
                    }
                },
                "required": ["belief_state"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "contradictions": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "consensus_groups": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "warnings": {"type": "array"}
                },
                "required": ["contradictions", "consensus_groups"]
            },
            deterministic=True
        )
    
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute contradiction detection with explicit payload."""
        from services.normalization.schemas import NormalizedClaim
        from core.schemas.claim import Polarity, ClaimSubtype
        from services.contradiction.schemas import AnalysisRequest
        
        belief_state_dict = payload.get("belief_state")
        if not belief_state_dict:
            raise ValueError("belief_state is required")
        
        # Reconstruct normalized claims
        claims = [
            self._build_normalized_claim(c) for c in belief_state_dict.get("claims", [])
        ]
        
        # Call service
        request = AnalysisRequest(
            claims=claims,
            value_tolerance_by_unit={}
        )
        
        result = self._service.analyze(request)
        
        return {
            "contradictions": [
                {
                    "claim_id_a": cont.claim_id_a,
                    "claim_id_b": cont.claim_id_b,
                    "reason": cont.reason.reason if hasattr(cont.reason, 'reason') else str(cont.reason),
                    "value_diff": cont.value_diff,
                    "unit": cont.unit
                }
                for cont in result.contradictions
            ],
            "consensus_groups": [
                {
                    "metric": group.metric_canonical if hasattr(group, 'metric_canonical') else group.get("metric"),
                    "claim_ids": group.claim_ids if hasattr(group, 'claim_ids') else group.get("claim_ids", []),
                    "agreement_score": group.agreement_score if hasattr(group, 'agreement_score') else group.get("agreement_score")
                }
                for group in result.consensus
            ],
            "warnings": []
        }
    
    def _build_normalized_claim(self, c_dict: Dict[str, Any]):
        """Build a NormalizedClaim from dict."""
        from core.schemas.normalized_claim import NormalizedClaim
        from core.schemas.claim import Polarity, ClaimSubtype
        
        # Resolve enums
        polarity = self._resolve_enum(Polarity, c_dict.get("polarity"), Polarity.NEUTRAL)
        subtype = self._resolve_enum(ClaimSubtype, c_dict.get("claim_subtype"), ClaimSubtype.ABSOLUTE)
        
        return NormalizedClaim(
            claim_id=c_dict.get("claim_id"),
            subject=c_dict.get("subject"),
            predicate=c_dict.get("predicate"),
            object_raw=c_dict.get("object_raw", ""),
            metric_canonical=c_dict.get("metric_canonical"),
            value_raw=c_dict.get("value_raw", ""),
            value_normalized=float(c_dict.get("value_normalized", 0.0)),
            unit_normalized=c_dict.get("unit_normalized"),
            polarity=polarity,
            context_id=c_dict.get("context_id"),
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
