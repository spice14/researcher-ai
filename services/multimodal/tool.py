"""Multimodal Extraction as MCP Tool — tables, figures, metrics.

Wraps multimodal.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.multimodal.service import MultimodalExtractionService


class MultimodalTool(MCPTool):
    """MCP wrapper for multimodal extraction service."""

    def __init__(self):
        """Initialize with internal service instance."""
        self._service = MultimodalExtractionService()

    def manifest(self) -> MCPManifest:
        """Define multimodal extraction tool interface."""
        return MCPManifest(
            name="multimodal",
            version="1.0.0",
            description="Extract tables, figures, and metrics from text chunks as structured data",
            input_schema={
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper identifier for provenance"
                    },
                    "chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "text": {"type": "string"},
                                "page": {"type": "integer"}
                            },
                            "required": ["text"]
                        },
                        "description": "Text chunks to extract artifacts from"
                    },
                    "page_constraint": {
                        "type": "integer",
                        "description": "Optional: restrict extraction to a specific page"
                    },
                    "pdf_path": {
                        "type": "string",
                        "description": "Optional: path to PDF for direct PyMuPDF extraction"
                    },
                    "link_to_claims": {
                        "type": "boolean",
                        "description": "Whether to link extracted metrics to claim IDs"
                    }
                },
                "required": ["paper_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "result_id": {"type": "string"},
                                "artifact_type": {"type": "string"},
                                "page_number": {"type": "integer"},
                                "raw_content": {},
                                "normalized_data": {"type": "object"},
                                "caption": {"type": "string"}
                            }
                        }
                    },
                    "extraction_count": {"type": "integer"},
                    "warnings": {"type": "array"}
                },
                "required": ["paper_id", "results", "extraction_count"]
            },
            deterministic=True
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multimodal extraction with explicit payload."""
        paper_id = payload.get("paper_id")
        chunks = payload.get("chunks", [])
        page_constraint = payload.get("page_constraint")
        pdf_path = payload.get("pdf_path")
        link_to_claims = payload.get("link_to_claims", False)

        if not paper_id:
            raise ValueError("paper_id is required")

        warnings = []

        # Use PDF path for direct PyMuPDF extraction if provided
        if pdf_path:
            results = self._service.extract_from_pdf(
                pdf_path=pdf_path,
                paper_id=paper_id,
                link_to_claims=link_to_claims,
            )
            return {
                "paper_id": paper_id,
                "results": results,
                "extraction_count": len(results),
                "warnings": warnings,
            }

        if not chunks:
            warnings.append("empty chunk list provided; no artifacts extracted")
            return {
                "paper_id": paper_id,
                "results": [],
                "extraction_count": 0,
                "warnings": warnings,
            }

        results = self._service.extract(
            paper_id=paper_id,
            chunks=chunks,
            page_constraint=page_constraint,
        )

        return {
            "paper_id": paper_id,
            "results": results,
            "extraction_count": len(results),
            "warnings": warnings,
        }
