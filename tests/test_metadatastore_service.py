"""Tests for the metadata store service — SQLite CRUD + persistence."""

import os
import tempfile
from datetime import datetime, timezone

import pytest

from services.metadatastore.service import MetadataStoreService
from services.metadatastore.schemas import (
    ClaimRecord,
    HypothesisRecord,
    PaperRecord,
    ProposalRecord,
    SessionRecord,
)
from services.metadatastore.tool import MetadataStoreTool


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_metadata.db")


@pytest.fixture
def svc(db_path):
    service = MetadataStoreService(db_path=db_path)
    yield service
    service.close()


class TestMetadataStoreService:
    """SQLite CRUD + persistence tests."""

    def test_save_and_get_paper(self, svc):
        paper = PaperRecord(
            paper_id="paper_001",
            title="Test Paper",
            authors=["Alice", "Bob"],
            abstract="An abstract.",
            doi="10.1234/test",
            pdf_path="/tmp/test.pdf",
            ingestion_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            chunk_count=10,
        )
        svc.save_paper(paper)
        retrieved = svc.get_paper("paper_001")
        assert retrieved is not None
        assert retrieved.title == "Test Paper"
        assert retrieved.authors == ["Alice", "Bob"]
        assert retrieved.chunk_count == 10

    def test_paper_not_found(self, svc):
        assert svc.get_paper("nonexistent") is None

    def test_list_papers(self, svc):
        svc.save_paper(PaperRecord(paper_id="p1", title="Paper 1"))
        svc.save_paper(PaperRecord(paper_id="p2", title="Paper 2"))
        papers = svc.list_papers()
        assert len(papers) == 2

    def test_save_and_get_claims(self, svc):
        svc.save_paper(PaperRecord(paper_id="p1", title="P1"))
        claims = [
            ClaimRecord(claim_id="c1", paper_id="p1", subject="BERT", predicate="achieves", object_value="92%"),
            ClaimRecord(claim_id="c2", paper_id="p1", subject="GPT", predicate="scores", object_value="88%"),
        ]
        count = svc.save_claims(claims)
        assert count == 2

        retrieved = svc.get_claims("p1")
        assert len(retrieved) == 2
        assert retrieved[0].claim_id == "c1"

    def test_save_and_get_session(self, svc):
        now = datetime.now(timezone.utc)
        session = SessionRecord(
            session_id="sess_001",
            user_input="analyze my paper",
            phase="ingestion",
            created_at=now,
            paper_ids=["p1", "p2"],
        )
        svc.save_session(session)
        retrieved = svc.get_session("sess_001")
        assert retrieved is not None
        assert retrieved.phase == "ingestion"
        assert retrieved.paper_ids == ["p1", "p2"]

    def test_save_and_get_hypothesis(self, svc):
        svc.save_session(SessionRecord(session_id="s1"))
        hyp = HypothesisRecord(
            hypothesis_id="hyp_001",
            session_id="s1",
            statement="X improves Y",
            confidence_score=0.7,
            iteration_number=2,
        )
        svc.save_hypothesis(hyp)
        retrieved = svc.get_hypothesis("hyp_001")
        assert retrieved is not None
        assert retrieved.confidence_score == 0.7

    def test_save_and_get_proposal(self, svc):
        svc.save_session(SessionRecord(session_id="s1"))
        svc.save_hypothesis(HypothesisRecord(hypothesis_id="h1", session_id="s1"))
        proposal = ProposalRecord(
            proposal_id="prop_001",
            hypothesis_id="h1",
            session_id="s1",
            markdown="# Proposal\nContent here.",
        )
        svc.save_proposal(proposal)
        retrieved = svc.get_proposal("prop_001")
        assert retrieved is not None
        assert "Content here" in retrieved.markdown

    def test_persistence_across_restart(self, db_path):
        svc1 = MetadataStoreService(db_path=db_path)
        svc1.save_paper(PaperRecord(paper_id="persist_test", title="Persistent"))
        svc1.close()

        svc2 = MetadataStoreService(db_path=db_path)
        retrieved = svc2.get_paper("persist_test")
        svc2.close()
        assert retrieved is not None
        assert retrieved.title == "Persistent"

    def test_upsert_paper(self, svc):
        svc.save_paper(PaperRecord(paper_id="p1", title="Original"))
        svc.save_paper(PaperRecord(paper_id="p1", title="Updated"))
        paper = svc.get_paper("p1")
        assert paper.title == "Updated"


class TestMetadataStoreTool:
    """MCP contract tests for the metadata store tool."""

    def test_manifest(self, db_path):
        svc = MetadataStoreService(db_path=db_path)
        tool = MetadataStoreTool(service=svc)
        m = tool.manifest()
        assert m.name == "metadata_store"
        assert "operation" in m.input_schema["properties"]
        svc.close()

    def test_save_and_get_paper_via_tool(self, db_path):
        svc = MetadataStoreService(db_path=db_path)
        tool = MetadataStoreTool(service=svc)

        tool.call({
            "operation": "save_paper",
            "data": {"paper_id": "tp1", "title": "Tool Paper"},
        })
        result = tool.call({
            "operation": "get_paper",
            "data": {"paper_id": "tp1"},
        })
        assert result["status"] == "ok"
        assert result["data"]["title"] == "Tool Paper"
        svc.close()

    def test_unknown_operation_raises(self, db_path):
        svc = MetadataStoreService(db_path=db_path)
        tool = MetadataStoreTool(service=svc)
        with pytest.raises(ValueError, match="Unknown operation"):
            tool.call({"operation": "nope"})
        svc.close()
