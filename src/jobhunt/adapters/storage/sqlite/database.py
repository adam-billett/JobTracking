"""
SQLite connection setup and migration runner.

Opening the database and bringing its schema up to date is a distinct
responsibility from reading/writing jobs, so it lives here rather than in
the repository. bootstrap.py calls connect() once and hands the resulting
connection to the repository.

Applied migrations are recorded in a schema_version table, so each one runs
exactly once per database. That matters from JT-2 on: SQLite cannot re-run
ALTER TABLE ... ADD COLUMN, so "run every file every time" no longer works.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(Exception):
    """Raised when the migrations folder holds a file the runner cannot order."""


def connect(database_path: str) -> sqlite3.Connection:
    """
    Open a SQLite connection and apply any pending migrations.

    `database_path` may be a file path or ":memory:" for an ephemeral
    in-memory database (used by tests). Rows are returned as sqlite3.Row
    so the repository can read columns by name rather than by position.
    """
    # SQLite creates the file but not its folder, so a fresh checkout would
    # fail on "data/jobs.db" until data/ exists. ":memory:" has no folder.
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless asked, per connection.
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    return connection


def apply_migrations(
    connection: sqlite3.Connection,
    migrations_dir: Path = _MIGRATIONS_DIR,
) -> list[int]:
    """
    Apply every migration newer than the database's current version, in
    order, and return the versions applied.

    Each migration and its version record are committed together, so a
    failing migration leaves the database exactly as it was before it.
    Migration files must not contain their own BEGIN/COMMIT.

    A database created before versioning existed reports version 0, so
    0001 runs again against it. That is safe only because 0001 uses
    CREATE TABLE IF NOT EXISTS, which is why that file must never change.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
        """
    )
    connection.commit()

    current = _current_version(connection)
    applied: list[int] = []
    for version, path in _discover(migrations_dir):
        if version <= current:
            continue
        _apply_one(connection, version, path)
        applied.append(version)
    return applied


def _current_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0]) if row[0] is not None else 0


def _discover(migrations_dir: Path) -> list[tuple[int, Path]]:
    # Refuse anything we can't order unambiguously. A misnamed or duplicate
    # file would otherwise be skipped or applied in the wrong order silently.
    found: dict[int, Path] = {}
    for path in sorted(migrations_dir.glob("*.sql")):
        match = _MIGRATION_NAME.match(path.name)
        if match is None:
            raise MigrationError(f"{path.name}: migration files must be named NNNN_description.sql")
        version = int(match.group(1))
        if version in found:
            raise MigrationError(
                f"{path.name}: version {version} is already used by {found[version].name}"
            )
        found[version] = path
    return sorted(found.items())


def _apply_one(connection: sqlite3.Connection, version: int, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    try:
        # executescript commits anything pending, then runs the script. The
        # leading BEGIN keeps the migration open so the version insert below
        # lands in the same transaction.
        connection.executescript("BEGIN;\n" + sql)
        connection.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
