"""Small forward-only migration runner for the local SQLite POC."""

from __future__ import annotations

import sqlite3
from pathlib import Path


MIGRATIONS = Path(__file__).with_name("migrations")


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply every numbered migration exactly once in filename order."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        if path.name in applied:
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (path.name,),
        )
        connection.commit()
