"""
SQLite implementation of the JobRepository port.

The only place sqlite3 is used for job storage. Takes an open connection
(opened and migrated by database.connect) so tests can pass an in-memory
connection and bootstrap can pass a file-backed one.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from jobhunt.domain.errors import JobNotFoundError
from jobhunt.domain.job import Job
from jobhunt.domain.job_application import JobApplication, Note
from jobhunt.domain.status import JobStatus


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
                "INSERT OR IGNORE INTO jobs"
                " (id, source, external_id, company, title, url, location, posted_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.id,
                    job.source,
                    job.external_id,
                    job.company,
                    job.title,
                    job.url,
                    job.location,
                    _to_text(job.posted_at),
                ),
            )
            inserted += cursor.rowcount
        self._connection.commit()
        return inserted

    def list_jobs(self) -> list[Job]:
        """Return all stored jobs."""
        rows = self._connection.execute(
            "SELECT id, source, external_id, company, title, url, location, posted_at FROM jobs"
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def get_job(self, job_id: str) -> Job | None:
        row = self._connection.execute(
            "SELECT id, source, external_id, company, title, url, location, posted_at"
            " FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        return _row_to_job(row) if row is not None else None

    def find_job_ids(self, prefix: str) -> list[str]:
        # substr comparison instead of LIKE: a prefix containing % or _
        # must match literally, not as a wildcard.
        rows = self._connection.execute(
            "SELECT id FROM jobs WHERE substr(id, 1, length(?)) = ? ORDER BY id",
            (prefix, prefix),
        ).fetchall()
        return [str(row["id"]) for row in rows]

    def get_application(self, job_id: str) -> JobApplication | None:
        row = self._connection.execute(
            "SELECT status, applied_at, tracking_url, contact FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None

        note_rows = self._connection.execute(
            "SELECT created_at, body FROM job_notes WHERE job_id = ? ORDER BY id",
            (job_id,),
        ).fetchall()

        return JobApplication(
            job_id=job_id,
            status=JobStatus(row["status"]),
            applied_at=_from_text(row["applied_at"]),
            tracking_url=row["tracking_url"],
            contact=row["contact"],
            notes=tuple(
                Note(created_at=datetime.fromisoformat(n["created_at"]), body=n["body"])
                for n in note_rows
            ),
        )

    def save_application(self, application: JobApplication) -> None:
        """
        Write the tracking fields and replace this job's notes, in one
        transaction. Notes are rewritten as a set because the domain object
        holds the full list; it is the source of truth.
        """
        job_id = application.job_id
        # "with connection" commits on success and rolls back on any error,
        # including the JobNotFoundError raised below.
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE jobs
                SET status = ?, applied_at = ?, tracking_url = ?, contact = ?
                WHERE id = ?
                """,
                (
                    application.status.value,
                    _to_text(application.applied_at),
                    application.tracking_url,
                    application.contact,
                    job_id,
                ),
            )
            if cursor.rowcount == 0:
                raise JobNotFoundError(job_id)

            self._connection.execute("DELETE FROM job_notes WHERE job_id = ?", (job_id,))
            self._connection.executemany(
                "INSERT INTO job_notes (job_id, created_at, body) VALUES (?, ?, ?)",
                [(job_id, note.created_at.isoformat(), note.body) for note in application.notes],
            )


def _row_to_job(row: sqlite3.Row) -> Job:
    # Rehydrating a stored job: the id already exists, so build Job directly
    # rather than through Job.create, which would re-derive it.
    return Job(
        id=row["id"],
        source=row["source"],
        external_id=row["external_id"],
        company=row["company"],
        title=row["title"],
        url=row["url"],
        location=row["location"],
        posted_at=_from_text(row["posted_at"]),
    )


def _to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _from_text(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
