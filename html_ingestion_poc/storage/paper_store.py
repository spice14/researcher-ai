"""Local paper storage — structured filesystem layout.

Storage layout per paper:
    papers/{source}_{id}/
        paper.md          — full markdown rendering
        metadata.json     — all metadata + extraction telemetry
        tables.json       — structured table data
        figures/          — figure metadata (URLs, captions)

Usage:
    store = PaperStore(base_dir=Path("papers"))
    store.store(doc)
    doc = store.load("arxiv_2401_12345")
    docs = store.list_papers()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from html_ingestion_poc.models.research_document import ResearchDocument

logger = logging.getLogger(__name__)


class PaperStore:
    """Filesystem-backed paper storage."""

    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def store(self, doc: ResearchDocument) -> Path:
        """Store a ResearchDocument to disk.

        Returns the paper directory path.
        """
        paper_dir = self._base / doc.id
        paper_dir.mkdir(parents=True, exist_ok=True)

        # paper.md — human-readable rendering
        md_path = paper_dir / "paper.md"
        md_path.write_text(doc.to_markdown(), encoding="utf-8")

        # metadata.json — full Pydantic model
        meta_path = paper_dir / "metadata.json"
        meta_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

        # tables.json — just the tables for easy access
        tables_path = paper_dir / "tables.json"
        tables_data = [t.model_dump() for t in doc.tables]
        tables_path.write_text(json.dumps(tables_data, indent=2), encoding="utf-8")

        # figures/ directory with metadata
        if doc.figures:
            fig_dir = paper_dir / "figures"
            fig_dir.mkdir(exist_ok=True)
            fig_meta = [f.model_dump() for f in doc.figures]
            (fig_dir / "figures.json").write_text(
                json.dumps(fig_meta, indent=2), encoding="utf-8"
            )

        logger.info("Stored %s → %s", doc.id, paper_dir)
        return paper_dir

    def load(self, paper_id: str) -> Optional[ResearchDocument]:
        """Load a ResearchDocument from disk.

        Returns None if not found.
        """
        meta_path = self._base / paper_id / "metadata.json"
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return ResearchDocument.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to load paper %s: %s", paper_id, exc)
            return None

    def list_papers(self) -> List[str]:
        """List all stored paper IDs."""
        ids = []
        for entry in sorted(self._base.iterdir()):
            if entry.is_dir() and (entry / "metadata.json").exists():
                ids.append(entry.name)
        return ids

    def exists(self, paper_id: str) -> bool:
        return (self._base / paper_id / "metadata.json").exists()

    def delete(self, paper_id: str) -> bool:
        """Delete a stored paper. Returns True if it existed."""
        paper_dir = self._base / paper_id
        if not paper_dir.exists():
            return False
        import shutil
        shutil.rmtree(paper_dir)
        logger.info("Deleted %s", paper_id)
        return True

    def get_paper_dir(self, paper_id: str) -> Optional[Path]:
        """Get the directory path for a paper."""
        d = self._base / paper_id
        return d if d.exists() else None
