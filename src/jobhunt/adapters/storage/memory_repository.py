"""
In-memory implementation of the JobRepository port.

Used by tests (fast, no I/O) and available as a lightweight non-persistent
store. Must behave identically to SqliteJobRepository — the shared contract
suite in tests/contract/ runs against both to guarantee that.
"""

from __future__ import annotations

from jobhunt.domain.errors import JobNotFoundError
from jobhunt.domain.job import Job
from jobhunt.domain.job_application import JobApplication


class InMemoryJobRepository:
    def __init__(self) -> None:
        # Keyed by job id so duplicate saves hit the same slot, mirroring
        # the SQLite primary-key dedup behavior.
        self._jobs: dict[str, Job] = {}
        self._applications: dict[str, JobApplication] = {}

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

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def find_job_ids(self, prefix: str) -> list[str]:
        return sorted(job_id for job_id in self._jobs if job_id.startswith(prefix))

    def get_application(self, job_id: str) -> JobApplication | None:
        if job_id not in self._jobs:
            return None
        return self._applications.get(job_id, JobApplication(job_id))

    def save_application(self, application: JobApplication) -> None:
        if application.job_id not in self._jobs:
            raise JobNotFoundError(application.job_id)
        self._applications[application.job_id] = application
