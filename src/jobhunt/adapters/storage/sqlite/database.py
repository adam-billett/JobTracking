"""
SQLite connection setup and migration runner.

Opening the database and bringing its schema up to date is a distinct
responsibility from reading/writing jobs, so it lives here rather than in
the repository. bootstrap.py calls connect() once and hands the resulting
connection to the repository.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(database_path: str) -> sqlite3.Connection:
    """
    Open a SQLite connection and apply any pending migrations.

    `database_path` may be a file path or ":memory:" for an ephemeral
    in-memory database (used by tests). Rows are returned as sqlite3.Row
    so the repository can read columns by name rather than by position.
    """
    # Ensure the parent directory exists — SQLite creates the file but not
    # the folder, so a path like "data/jobs.db" fails on a fresh checkout
    # until data/ exists. ":memory:" has no parent, so skip it.
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    _apply_migrations(connection)
    return connection


def _apply_migrations(connection: sqlite3.Connection) -> None:
    # MVP migration strategy: run every .sql file in order. Each uses
    # CREATE TABLE IF NOT EXISTS, so re-running is harmless. A real
    # schema_version table (per §5) arrives when the first migration that
    # can't be made idempotent does — not needed yet for one table.
    for migration_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        sql = migration_file.read_text(encoding="utf-8")
        connection.executescript(sql)
    connection.commit()
