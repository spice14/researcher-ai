"""Normalization Service as MCP Tool — metric canonicalization and binding.

Wraps normalization.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.normalization.service import NormalizationService


class NormalizationTool(MCPTool):
    """MCP wrapper for normalization service."""
    
    def __init__(self):
        """Initialize with internal service instance."""
        self._service = NormalizationService()
    
    
    def manifest(self) -> MCPManifest:
        """Define normalization tool interface."""
        return MCPManifest(
            name="normalization",
            version="1.0.0",
            description="Canonicalize metric names and bind numeric values deterministically",
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Claims with metric names to normalize"
                    },
                    "debug_mode": {
                        "type": "boolean",
                        "default": False,
                        "description": "Enable diagnostic output"
                    }
                },
                "required": ["claims"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "normalized_claims": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "failed_normalizations": {"type": "array"},
                    "warnings": {"type": "array"}
                },
                "required": ["normalized_claims"]
            },
            deterministic=True
        )
    
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute normalization with explicit payload."""
        from core.schemas.claim import Claim, ClaimEvidence, ClaimSubtype, Polarity
        from services.normalization.schemas import NormalizationRequest
        
        claims = payload.get("claims", [])
        debug_mode = payload.get("debug_mode", False)
        
        if not claims:
            # Empty input → empty output (graceful degradation)
            return {
                "normalized_claims": [],
                "failed_normalizations": [],
                "warnings": []
            }
        
        # Build claim objects
        claim_objs = [self._build_claim(c) for c in claims]
        
        # Normalize claims
        normalized_claims = []
        for claim in claim_objs:
            result = self._service.normalize(
                NormalizationRequest(claim=claim),
                debug_mode=debug_mode
            )
            if result.normalized:
                normalized_claims.append(result.normalized)
        
        return self._format_output(normalized_claims)
    
    def _build_claim(self, claim_dict: Dict[str, Any]):
        """Build a Claim object from dict."""
        from core.schemas.claim import Claim, ClaimEvidence, ClaimSubtype, Polarity
        
        polarity = self._resolve_enum(Polarity, claim_dict.get("polarity", "neutral"), Polarity.NEUTRAL)
        subtype = self._resolve_enum(ClaimSubtype, claim_dict.get("claim_subtype", "absolute"), ClaimSubtype.ABSOLUTE)
        
        evidence = [
            ClaimEvidence(
                source_id=ev.get("source_id"),
                page=ev.get("page"),
                snippet=ev.get("snippet"),
                retrieval_score=ev.get("retrieval_score")
            )
            for ev in claim_dict.get("evidence", [])
        ]
        
        return Claim(
            claim_id=claim_dict.get("claim_id"),
            subject=claim_dict.get("subject"),
            predicate=claim_dict.get("predicate"),
            object=claim_dict.get("object"),
            polarity=polarity,
            confidence_level=claim_dict.get("confidence_level", 0.5),
            evidence=evidence,
            context_id=claim_dict.get("context_id"),
            claim_subtype=subtype
        )
    
    def _resolve_enum(self, enum_cls, value: Any, default: Any):
        """Resolve a value to its enum."""
        if isinstance(value, enum_cls):
            return value
        if not isinstance(value, str):
            return default
        # Try by value or name
        try:
            for member in enum_cls.__members__.values():
                if member.value == value or member.name == value.upper():
                    return member
        except (AttributeError, TypeError):
            pass
        return default
    
    def _format_output(self, normalized_claims: list) -> Dict[str, Any]:
        """Format normalized claims for output."""
        return {
            "normalized_claims": [
                {
                    "claim_id": nc.claim_id,
                    "subject": nc.subject,
                    "predicate": nc.predicate,
                    "object_raw": nc.object_raw,
                    "metric_canonical": nc.metric_canonical,
                    "value_raw": nc.value_raw,
                    "value_normalized": nc.value_normalized,
                    "unit_normalized": nc.unit_normalized,
                    "polarity": nc.polarity.value if hasattr(nc.polarity, 'value') else str(nc.polarity),
                    "context_id": nc.context_id,
                    "claim_subtype": nc.claim_subtype.value if hasattr(nc.claim_subtype, 'value') else str(nc.claim_subtype)
                }
                for nc in normalized_claims
            ],
            "warnings": []
        }
