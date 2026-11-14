"""
Track application use case.

Turns a job reference typed on the command line (a full id or any unique
prefix of one) into a job, then applies one tracking action to it: mark
applied, update the link/contact, or add a note. The clock is injected, so
"date applied is recorded automatically" is testable with a fixed time.

Depends only on ports. Returns data (TrackedJob) and never prints, so the
CLI decides how results look.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobhunt.domain.errors import AmbiguousJobReferenceError, JobNotFoundError
from jobhunt.domain.job import Job
from jobhunt.domain.job_application import JobApplication
from jobhunt.ports.clock import Clock
from jobhunt.ports.job_repository import JobRepository


@dataclass(frozen=True)
class TrackedJob:
    """A posting together with where my application to it stands."""

    job: Job
    application: JobApplication


class TrackApplicationService:
    def __init__(self, repository: JobRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def apply(
        self,
        reference: str,
        *,
        tracking_url: str | None = None,
        contact: str | None = None,
    ) -> TrackedJob:
        """Mark a job applied now, optionally saving its link and a contact."""
        tracked = self._load(reference)
        updated = tracked.application.mark_applied(
            self._clock.now(), tracking_url=tracking_url, contact=contact
        )
        self._repository.save_application(updated)
        return TrackedJob(tracked.job, updated)

    def update_details(
        self,
        reference: str,
        *,
        tracking_url: str | None = None,
        contact: str | None = None,
    ) -> TrackedJob:
        """Save a tracking link and/or contact without changing the status."""
        tracked = self._load(reference)
        updated = tracked.application.update_details(tracking_url=tracking_url, contact=contact)
        self._repository.save_application(updated)
        return TrackedJob(tracked.job, updated)

    def add_note(self, reference: str, body: str) -> TrackedJob:
        """Append a note, dated now."""
        tracked = self._load(reference)
        updated = tracked.application.add_note(self._clock.now(), body)
        self._repository.save_application(updated)
        return TrackedJob(tracked.job, updated)

    def show(self, reference: str) -> TrackedJob:
        """Return one job and its tracking record."""
        return self._load(reference)

    def list_tracked(self) -> list[TrackedJob]:
        """Return every stored job with its tracking record."""
        tracked: list[TrackedJob] = []
        for job in self._repository.list_jobs():
            application = self._repository.get_application(job.id) or JobApplication(job.id)
            tracked.append(TrackedJob(job, application))
        return tracked

    def _load(self, reference: str) -> TrackedJob:
        job_id = self._resolve(reference)
        job = self._repository.get_job(job_id)
        application = self._repository.get_application(job_id)
        if job is None or application is None:
            raise JobNotFoundError(reference)
        return TrackedJob(job, application)

    def _resolve(self, reference: str) -> str:
        # Ids are lowercase hex, so normalize what was typed. An empty
        # reference would match every job; treat it as matching none.
        prefix = reference.strip().lower()
        if not prefix:
            raise JobNotFoundError(reference)

        matches = self._repository.find_job_ids(prefix)
        if not matches:
            raise JobNotFoundError(reference)
        if len(matches) > 1:
            raise AmbiguousJobReferenceError(reference, matches)
        return matches[0]
