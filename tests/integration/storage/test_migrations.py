"""
Integration tests for the SQLite migration runner.

These use real database files in a temp directory, because what's under
test (what persists between connections, what a failed migration leaves
behind) only shows up on a real file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jobhunt.adapters.storage.sqlite import database
from jobhunt.adapters.storage.sqlite.database import MigrationError, apply_migrations, connect


def _write(directory: Path, name: str, sql: str) -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def _open(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _versions(connection: sqlite3.Connection) -> list[int]:
    rows = connection.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
    return [int(row["version"]) for row in rows]


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "migrations"
    directory.mkdir()
    _write(directory, "0001_create_a.sql", "CREATE TABLE a (id INTEGER PRIMARY KEY);")
    _write(directory, "0002_add_b.sql", "ALTER TABLE a ADD COLUMN b TEXT;")
    return directory


class TestApplyMigrations:
    def test_fresh_database_applies_all_in_order(
        self, tmp_path: Path, migrations_dir: Path
    ) -> None:
        connection = _open(tmp_path / "test.db")
        assert apply_migrations(connection, migrations_dir) == [1, 2]
        assert _versions(connection) == [1, 2]

    def test_second_run_applies_nothing(self, tmp_path: Path, migrations_dir: Path) -> None:
        connection = _open(tmp_path / "test.db")
        apply_migrations(connection, migrations_dir)
        assert apply_migrations(connection, migrations_dir) == []

    def test_only_new_migrations_run(self, tmp_path: Path, migrations_dir: Path) -> None:
        connection = _open(tmp_path / "test.db")
        apply_migrations(connection, migrations_dir)
        _write(migrations_dir, "0003_add_c.sql", "ALTER TABLE a ADD COLUMN c TEXT;")

        assert apply_migrations(connection, migrations_dir) == [3]
        assert "c" in _columns(connection, "a")

    def test_failed_migration_is_rolled_back_and_not_recorded(
        self, tmp_path: Path, migrations_dir: Path
    ) -> None:
        # The first statement is valid, the second is not. Neither may stick.
        _write(
            migrations_dir,
            "0003_broken.sql",
            "ALTER TABLE a ADD COLUMN c TEXT;\nTHIS IS NOT SQL;",
        )
        connection = _open(tmp_path / "test.db")

        with pytest.raises(sqlite3.Error):
            apply_migrations(connection, migrations_dir)

        assert _versions(connection) == [1, 2]
        assert "c" not in _columns(connection, "a")

    def test_badly_named_file_raises(self, tmp_path: Path, migrations_dir: Path) -> None:
        _write(migrations_dir, "add_c.sql", "ALTER TABLE a ADD COLUMN c TEXT;")
        with pytest.raises(MigrationError):
            apply_migrations(_open(tmp_path / "test.db"), migrations_dir)

    def test_duplicate_version_raises(self, tmp_path: Path, migrations_dir: Path) -> None:
        _write(migrations_dir, "0002_other.sql", "ALTER TABLE a ADD COLUMN c TEXT;")
        with pytest.raises(MigrationError):
            apply_migrations(_open(tmp_path / "test.db"), migrations_dir)


class TestUpgradeExistingDatabase:
    def test_database_from_before_versioning_keeps_its_jobs(self, tmp_path: Path) -> None:
        # Recreate a JT-1 database: jobs table and a row, no schema_version.
        path = tmp_path / "jobs.db"
        initial_sql = (
            Path(database.__file__).parent / "migrations" / "0001_initial.sql"
        ).read_text(encoding="utf-8")
        legacy = sqlite3.connect(path)
        legacy.executescript(initial_sql)
        legacy.execute(
            "INSERT INTO jobs (id, source, external_id, company, title, url, location, posted_at)"
            " VALUES ('abc', 'greenhouse', '1', 'Acme', 'Engineer', 'https://x/1', NULL, NULL)"
        )
        legacy.commit()
        legacy.close()

        connection = connect(str(path))

        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert 1 in _versions(connection)
