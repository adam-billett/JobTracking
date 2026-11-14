"""
JobRepository port.

The contract for storing and retrieving collected jobs and my applications
to them. Implemented by the SQLite adapter (durable, between-runs storage)
and the in-memory adapter (tests and lightweight use). The application
layer depends only on this interface, never on sqlite3.
"""

from __future__ import annotations

from typing import Protocol

from jobhunt.domain.job import Job
from jobhunt.domain.job_application import JobApplication


class JobRepository(Protocol):
    def save_jobs(self, jobs: list[Job]) -> int:
        """
        Persist the given jobs, skipping any already stored (identified by
        source + external_id). Returns the count of newly-added jobs so the
        caller can report how many were genuinely new this run.
        """
        ...

    def list_jobs(self) -> list[Job]:
        """Return all stored jobs."""
        ...

    def get_job(self, job_id: str) -> Job | None:
        """Return the job with this exact id, or None if there is none."""
        ...

    def find_job_ids(self, prefix: str) -> list[str]:
        """
        Return the ids of every stored job whose id starts with `prefix`.
        Callers decide what zero or several matches mean.
        """
        ...

    def get_application(self, job_id: str) -> JobApplication | None:
        """
        Return the tracking record for a job, or None if the job does not
        exist. A job I haven't acted on yet has a default record with
        status NEW and no notes.
        """
        ...

    def save_application(self, application: JobApplication) -> None:
        """
        Store the full tracking record, notes included. Raises
        JobNotFoundError if the job does not exist.
        """
        ...
