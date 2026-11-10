"""
SQLite implementation of the JobRepository port.

The only place sqlite3 is used for job storage. Takes an open connection
(opened and migrated by database.connect) so tests can pass an in-memory
connection and bootstrap can pass a file-backed one.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from jobhunt.domain.job import Job


class SqliteJobRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_jobs(self, jobs: list[Job]) -> int:
        """
        Insert jobs, skipping any whose id already exists. Returns the
        number of rows actually inserted (new jobs this run).

        Dedup is enforced by the primary key via INSERT OR IGNORE: a
        repeated job id is silently skipped rather than raising, so
        re-running a search never errors and never duplicates.
        """
        inserted = 0
        for job in jobs:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO jobs
                    (id, source, external_id, company, title, url, location, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.source,
                    job.external_id,
                    job.company,
                    job.title,
                    job.url,
                    job.location,
                    job.posted_at.isoformat() if job.posted_at else None,
                ),
            )
            inserted += cursor.rowcount
        self._connection.commit()
        return inserted

    def list_jobs(self) -> list[Job]:
        """Return all stored jobs."""
        rows = self._connection.execute(
            """
            SELECT id, source, external_id, company, title, url, location, posted_at
            FROM jobs
            """
        ).fetchall()
        return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            source=row["source"],
            external_id=row["external_id"],
            company=row["company"],
            title=row["title"],
            url=row["url"],
            location=row["location"],
            posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        )
