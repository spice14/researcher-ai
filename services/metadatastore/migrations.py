"""DDL migrations for the metadata store SQLite database."""

TABLES = {
    "papers": """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors TEXT DEFAULT '[]',
            abstract TEXT,
            doi TEXT,
            arxiv_id TEXT,
            pdf_path TEXT DEFAULT '',
            ingestion_timestamp TEXT,
            chunk_count INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        )
    """,
    "claims": """
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            paper_id TEXT NOT NULL,
            text TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            predicate TEXT DEFAULT '',
            object_value TEXT DEFAULT '',
            claim_type TEXT DEFAULT 'performance',
            context_id TEXT,
            confidence_level TEXT DEFAULT 'low',
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
        )
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_input TEXT DEFAULT '',
            phase TEXT DEFAULT 'init',
            created_at TEXT,
            updated_at TEXT,
            paper_ids TEXT DEFAULT '[]',
            hypothesis_ids TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}'
        )
    """,
    "hypotheses": """
        CREATE TABLE IF NOT EXISTS hypotheses (
            hypothesis_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            statement TEXT DEFAULT '',
            confidence_score REAL,
            iteration_number INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """,
    "proposals": """
        CREATE TABLE IF NOT EXISTS proposals (
            proposal_id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            markdown TEXT DEFAULT '',
            created_at TEXT,
            FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(hypothesis_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """,
}


def run_migrations(conn) -> None:
    """Execute all DDL migrations."""
    cursor = conn.cursor()
    for table_name, ddl in TABLES.items():
        cursor.execute(ddl)
    conn.commit()
