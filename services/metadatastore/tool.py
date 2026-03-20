"""Metadata Store as MCP Tool — persistent structured metadata."""

from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from services.metadatastore.service import MetadataStoreService
from services.metadatastore.schemas import (
    ClaimRecord,
    HypothesisRecord,
    PaperRecord,
    ProposalRecord,
    SessionRecord,
)


class MetadataStoreTool(MCPTool):
    """MCP wrapper for the metadata store service."""

    def __init__(self, service: MetadataStoreService | None = None) -> None:
        self._service = service or MetadataStoreService()

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="metadata_store",
            version="1.0.0",
            description="Persistent SQLite metadata store for papers, claims, sessions, hypotheses, proposals",
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "save_paper", "get_paper", "list_papers",
                            "save_claims", "get_claims",
                            "save_session", "get_session",
                            "save_hypothesis", "get_hypothesis",
                            "save_proposal", "get_proposal",
                        ],
                        "description": "Operation to perform",
                    },
                    "data": {"type": "object", "description": "Operation-specific data"},
                },
                "required": ["operation"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "data": {"type": "object"},
                },
            },
            deterministic=True,
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        operation = payload.get("operation")
        data = payload.get("data", {})

        if not operation:
            raise ValueError("operation is required")

        if operation == "save_paper":
            record = PaperRecord(**data)
            self._service.save_paper(record)
            return {"status": "ok", "paper_id": record.paper_id}

        elif operation == "get_paper":
            paper = self._service.get_paper(data.get("paper_id", ""))
            return {"status": "ok", "data": paper.model_dump(mode="json") if paper else None}

        elif operation == "list_papers":
            papers = self._service.list_papers()
            return {"status": "ok", "data": [p.model_dump(mode="json") for p in papers]}

        elif operation == "save_claims":
            records = [ClaimRecord(**c) for c in data.get("claims", [])]
            count = self._service.save_claims(records)
            return {"status": "ok", "count": count}

        elif operation == "get_claims":
            claims = self._service.get_claims(data.get("paper_id", ""))
            return {"status": "ok", "data": [c.model_dump(mode="json") for c in claims]}

        elif operation == "save_session":
            record = SessionRecord(**data)
            self._service.save_session(record)
            return {"status": "ok", "session_id": record.session_id}

        elif operation == "get_session":
            session = self._service.get_session(data.get("session_id", ""))
            return {"status": "ok", "data": session.model_dump(mode="json") if session else None}

        elif operation == "save_hypothesis":
            record = HypothesisRecord(**data)
            self._service.save_hypothesis(record)
            return {"status": "ok", "hypothesis_id": record.hypothesis_id}

        elif operation == "get_hypothesis":
            hyp = self._service.get_hypothesis(data.get("hypothesis_id", ""))
            return {"status": "ok", "data": hyp.model_dump(mode="json") if hyp else None}

        elif operation == "save_proposal":
            record = ProposalRecord(**data)
            self._service.save_proposal(record)
            return {"status": "ok", "proposal_id": record.proposal_id}

        elif operation == "get_proposal":
            prop = self._service.get_proposal(data.get("proposal_id", ""))
            return {"status": "ok", "data": prop.model_dump(mode="json") if prop else None}

        else:
            raise ValueError(f"Unknown operation: {operation}")
