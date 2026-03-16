"""Extraction Service as MCP Tool — claim and evidence extraction.

Wraps extraction.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.extraction.service import ClaimExtractor


class ExtractionTool(MCPTool):
    """MCP wrapper for extraction service."""
    
    def __init__(self):
        """Initialize with internal service instance."""
        self._service = ClaimExtractor()
    
    def manifest(self) -> MCPManifest:
        """Define extraction tool interface."""
        return MCPManifest(
            name="extraction",
            version="1.0.0",
            description="Extract claims and evidence from text chunks",
            input_schema={
                "type": "object",
                "properties": {
                    "chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "text": {"type": "string"},
                                "source_id": {"type": "string"}
                            },
                            "required": ["chunk_id", "text", "source_id"]
                        }
                    },
                    "source_id": {
                        "type": "string",
                        "description": "Paper identifier"
                    }
                },
                "required": ["chunks", "source_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "claims": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "discarded_claims": {"type": "array"},
                    "warnings": {"type": "array"}
                },
                "required": ["source_id", "claims"]
            },
            deterministic=True
        )
    
    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute extraction with explicit payload.
        
        Args:
            payload: Must contain chunks list and source_id
        
        Returns:
            Result dict with claims and discarded_claims
        """
        # Extract parameters
        chunks = payload.get("chunks", [])
        source_id = payload.get("source_id")
        
        if not source_id:
            raise ValueError("source_id is required")
        if not chunks:
            raise ValueError("chunks cannot be empty")
        
        # Call service via canonical interface
        from services.extraction.schemas import ClaimExtractionRequest
        from services.ingestion.schemas import IngestionChunk
        
        reconstructed_chunks = []
        for chunk_dict in chunks:
            # Reconstruct IngestionChunk from dict
            reconstructed_chunks.append(
                IngestionChunk(
                    chunk_id=chunk_dict.get("chunk_id"),
                    text=chunk_dict.get("text"),
                    source_id=chunk_dict.get("source_id", source_id),
                    start_char=chunk_dict.get("start_char", 0),
                    end_char=chunk_dict.get("end_char", len(chunk_dict.get("text", ""))),
                    text_hash=chunk_dict.get("text_hash", ""),
                    context_id=chunk_dict.get("context_id", ""),
                    numeric_strings=chunk_dict.get("numeric_strings", []),
                    unit_strings=chunk_dict.get("unit_strings", []),
                    metric_names=chunk_dict.get("metric_names", []),
                )
            )

        all_claims = self._service.extract(reconstructed_chunks)

        discarded_count = 0
        for chunk in reconstructed_chunks:
            request = ClaimExtractionRequest(chunk=chunk)
            results = self._service._extract_all(request)
            discarded_count += sum(1 for result in results if result.no_claim)
        
        # Return as explicit dict
        return {
            "source_id": source_id,
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "object": claim.object,
                    "polarity": claim.polarity.value if hasattr(claim.polarity, 'value') else str(claim.polarity),
                    "confidence_level": claim.confidence_level,
                    "evidence": [
                        {
                            "source_id": ev.source_id,
                            "page": ev.page,
                            "snippet": ev.snippet,
                            "retrieval_score": ev.retrieval_score
                        }
                        for ev in claim.evidence
                    ],
                    "context_id": claim.context_id,
                    "claim_subtype": claim.claim_subtype.value if hasattr(claim.claim_subtype, 'value') else str(claim.claim_subtype)
                }
                for claim in all_claims
            ],
            "discarded_claims": discarded_count,
            "warnings": []
        }
