"""
In-memory implementation of the JobRepository port.

Used by tests (fast, no I/O) and available as a lightweight non-persistent
store. Must behave identically to SqliteJobRepository — the shared contract
suite in tests/contract/ runs against both to guarantee that.
"""

from __future__ import annotations

from jobhunt.domain.job import Job


class InMemoryJobRepository:
    def __init__(self) -> None:
        # Keyed by job id so duplicate saves overwrite the same slot,
        # mirroring the SQLite primary-key dedup behavior.
        self._jobs: dict[str, Job] = {}

    def save_jobs(self, jobs: list[Job]) -> int:
        """Store jobs, skipping ids already present. Returns count of new jobs."""
        inserted = 0
        for job in jobs:
            if job.id not in self._jobs:
                self._jobs[job.id] = job
                inserted += 1
        return inserted

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())
