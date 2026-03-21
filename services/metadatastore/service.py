"""Metadata store service wrapping SQLite for structured persistence.

Purpose:
- CRUD operations for papers, claims, sessions, hypotheses, proposals
- SQLite backend with auto-migration on init
- All state survives process restart

Failure Modes:
- Database path not writable -> raise RuntimeError
- Duplicate IDs -> upsert behavior
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from services.metadatastore.migrations import run_migrations
from services.metadatastore.schemas import (
    ClaimRecord,
    HypothesisRecord,
    PaperRecord,
    ProposalRecord,
    SessionRecord,
)

logger = logging.getLogger(__name__)


class MetadataStoreService:
    """SQLite-backed metadata store with automatic migration."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.environ.get("SQLITE_PATH", ".local/scholaros.db")
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        run_migrations(self._conn)
        logger.info("MetadataStore initialized at %s", self._db_path)

    def close(self) -> None:
        self._conn.close()

    # ── Papers ──

    def save_paper(self, paper: PaperRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO papers
               (paper_id, title, authors, abstract, doi, arxiv_id, pdf_path,
                ingestion_timestamp, chunk_count, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper.paper_id,
                paper.title,
                json.dumps(paper.authors),
                paper.abstract,
                paper.doi,
                paper.arxiv_id,
                paper.pdf_path,
                paper.ingestion_timestamp.isoformat() if paper.ingestion_timestamp else None,
                paper.chunk_count,
                json.dumps(paper.metadata),
            ),
        )
        self._conn.commit()

    def get_paper(self, paper_id: str) -> Optional[PaperRecord]:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        if not row:
            return None
        return PaperRecord(
            paper_id=row["paper_id"],
            title=row["title"],
            authors=json.loads(row["authors"]) if row["authors"] else [],
            abstract=row["abstract"],
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            pdf_path=row["pdf_path"] or "",
            ingestion_timestamp=datetime.fromisoformat(row["ingestion_timestamp"])
            if row["ingestion_timestamp"]
            else None,
            chunk_count=row["chunk_count"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def list_papers(self) -> List[PaperRecord]:
        rows = self._conn.execute("SELECT * FROM papers ORDER BY paper_id").fetchall()
        return [
            PaperRecord(
                paper_id=r["paper_id"],
                title=r["title"],
                authors=json.loads(r["authors"]) if r["authors"] else [],
                abstract=r["abstract"],
                doi=r["doi"],
                arxiv_id=r["arxiv_id"],
                pdf_path=r["pdf_path"] or "",
                ingestion_timestamp=datetime.fromisoformat(r["ingestion_timestamp"])
                if r["ingestion_timestamp"]
                else None,
                chunk_count=r["chunk_count"],
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    # ── Claims ──

    def save_claims(self, claims: List[ClaimRecord]) -> int:
        for claim in claims:
            self._conn.execute(
                """INSERT OR REPLACE INTO claims
                   (claim_id, paper_id, text, subject, predicate, object_value,
                    claim_type, context_id, confidence_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    claim.claim_id,
                    claim.paper_id,
                    claim.text,
                    claim.subject,
                    claim.predicate,
                    claim.object_value,
                    claim.claim_type,
                    claim.context_id,
                    claim.confidence_level,
                ),
            )
        self._conn.commit()
        return len(claims)

    def get_claims(self, paper_id: str) -> List[ClaimRecord]:
        rows = self._conn.execute(
            "SELECT * FROM claims WHERE paper_id = ?", (paper_id,)
        ).fetchall()
        return [
            ClaimRecord(
                claim_id=r["claim_id"],
                paper_id=r["paper_id"],
                text=r["text"],
                subject=r["subject"],
                predicate=r["predicate"],
                object_value=r["object_value"],
                claim_type=r["claim_type"],
                context_id=r["context_id"],
                confidence_level=r["confidence_level"],
            )
            for r in rows
        ]

    # ── Sessions ──

    def save_session(self, session: SessionRecord) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO sessions
               (session_id, user_input, phase, created_at, updated_at,
                paper_ids, hypothesis_ids, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.user_input,
                session.phase,
                session.created_at.isoformat() if session.created_at else now,
                session.updated_at.isoformat() if session.updated_at else now,
                json.dumps(session.paper_ids),
                json.dumps(session.hypothesis_ids),
                json.dumps(session.metadata),
            ),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            user_input=row["user_input"],
            phase=row["phase"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            paper_ids=json.loads(row["paper_ids"]) if row["paper_ids"] else [],
            hypothesis_ids=json.loads(row["hypothesis_ids"]) if row["hypothesis_ids"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    # ── Hypotheses ──

    def save_hypothesis(self, hyp: HypothesisRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO hypotheses
               (hypothesis_id, session_id, statement, confidence_score,
                iteration_number, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                hyp.hypothesis_id,
                hyp.session_id,
                hyp.statement,
                hyp.confidence_score,
                hyp.iteration_number,
                hyp.created_at.isoformat() if hyp.created_at else None,
            ),
        )
        self._conn.commit()

    def get_hypothesis(self, hypothesis_id: str) -> Optional[HypothesisRecord]:
        row = self._conn.execute(
            "SELECT * FROM hypotheses WHERE hypothesis_id = ?", (hypothesis_id,)
        ).fetchone()
        if not row:
            return None
        return HypothesisRecord(
            hypothesis_id=row["hypothesis_id"],
            session_id=row["session_id"],
            statement=row["statement"],
            confidence_score=row["confidence_score"],
            iteration_number=row["iteration_number"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    # ── Proposals ──

    def save_proposal(self, proposal: ProposalRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO proposals
               (proposal_id, hypothesis_id, session_id, markdown, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                proposal.proposal_id,
                proposal.hypothesis_id,
                proposal.session_id,
                proposal.markdown,
                proposal.created_at.isoformat() if proposal.created_at else None,
            ),
        )
        self._conn.commit()

    def get_proposal(self, proposal_id: str) -> Optional[ProposalRecord]:
        row = self._conn.execute(
            "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        if not row:
            return None
        return ProposalRecord(
            proposal_id=row["proposal_id"],
            hypothesis_id=row["hypothesis_id"],
            session_id=row["session_id"],
            markdown=row["markdown"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )
