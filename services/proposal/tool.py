"""Proposal Service as MCP Tool — research artifact generation.

Wraps proposal.service with explicit input/output contracts.
Zero behavioral change from original service.
"""

from typing import Dict, Any
from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.proposal.service import ProposalService


class ProposalTool(MCPTool):
    """MCP wrapper for proposal generation service."""

    def __init__(self):
        """Initialize with internal service instance."""
        self._service = ProposalService()

    def manifest(self) -> MCPManifest:
        """Define proposal tool interface."""
        return MCPManifest(
            name="proposal",
            version="1.0.0",
            description="Generate structured research proposals from validated hypotheses and evidence",
            input_schema={
                "type": "object",
                "properties": {
                    "hypothesis_id": {
                        "type": "string",
                        "description": "Validated hypothesis identifier"
                    },
                    "statement": {
                        "type": "string",
                        "description": "Hypothesis statement text"
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Hypothesis rationale"
                    },
                    "assumptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit assumptions"
                    },
                    "supporting_claims": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Supporting claim dicts"
                    },
                    "known_risks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Known risks"
                    },
                    "critiques": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Critique dicts"
                    },
                    "paper_references": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Paper reference dicts"
                    },
                    "constraints": {
                        "type": "object",
                        "description": "Optional constraints"
                    }
                },
                "required": ["hypothesis_id", "statement"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string"},
                    "hypothesis_id": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "full_markdown": {"type": "string"},
                    "references": {"type": "array"},
                    "warnings": {"type": "array"}
                },
                "required": ["proposal_id", "hypothesis_id", "sections", "full_markdown"]
            },
            deterministic=True
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute proposal generation with explicit payload."""
        from services.proposal.schemas import ProposalRequest

        hypothesis_id = payload.get("hypothesis_id")
        statement = payload.get("statement")

        if not hypothesis_id:
            raise ValueError("hypothesis_id is required")
        if not statement:
            raise ValueError("statement is required")

        request = ProposalRequest(
            hypothesis_id=hypothesis_id,
            statement=statement,
            rationale=payload.get("rationale", ""),
            assumptions=payload.get("assumptions", []),
            supporting_claims=payload.get("supporting_claims", []),
            known_risks=payload.get("known_risks", []),
            critiques=payload.get("critiques", []),
            paper_references=payload.get("paper_references", []),
            constraints=payload.get("constraints", {}),
        )

        result = self._service.generate(request)

        return {
            "proposal_id": result.proposal_id,
            "hypothesis_id": result.hypothesis_id,
            "sections": [
                {
                    "section": s.section.value,
                    "heading": s.heading,
                    "content": s.content,
                    "citations_used": s.citations_used,
                }
                for s in result.sections
            ],
            "full_markdown": result.full_markdown,
            "references": result.references,
            "warnings": result.warnings,
        }
