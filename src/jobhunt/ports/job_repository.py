"""
JobRepository port.

The contract for storing and retrieving collected jobs. Implemented by
the SQLite adapter (durable, between-runs storage) and the in-memory
adapter (tests and lightweight use). The application layer depends only
on this interface, never on sqlite3.
"""

from __future__ import annotations

from typing import Protocol

from jobhunt.domain.job import Job


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
