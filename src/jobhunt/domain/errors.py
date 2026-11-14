"""
Domain error types.

Defining our own errors (rather than leaking requests.HTTPError or
sqlite3.Error upward) keeps the application layer independent of which
adapter raised the problem. A failure fetching one company is an
expected, recoverable condition — not a crash — so it gets its own type
the use case can catch and report per-company.
"""

from __future__ import annotations

from datetime import datetime

from jobhunt.domain.status import JobStatus


class JobHuntError(Exception):
    """Base class for all errors this application raises deliberately."""


class JobSourceError(JobHuntError):
    """
    Raised when a job source fails to return usable data for one company
    (network failure, unexpected response, company not found). Carries the
    company identifier so the caller can report which one failed while
    continuing with the others.
    """

    def __init__(self, company: str, message: str):
        self.company = company
        super().__init__(f"[{company}] {message}")


class AlreadyAppliedError(JobHuntError):
    """
    Raised when marking a job applied that is already applied. Refusing,
    rather than overwriting, keeps the original applied date intact.
    """

    def __init__(self, job_id: str, applied_at: datetime | None) -> None:
        self.job_id = job_id
        self.applied_at = applied_at
        when = f" on {applied_at.date().isoformat()}" if applied_at else ""
        super().__init__(f"Already applied to this job{when}.")


class InvalidStatusTransitionError(JobHuntError):
    """Raised when a status change is not allowed by domain/status.py."""

    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot change status from '{current}' to '{target}'.")


class EmptyNoteError(JobHuntError):
    """Raised when a note has no text."""

    def __init__(self) -> None:
        super().__init__("A note needs some text.")


class JobNotFoundError(JobHuntError):
    """Raised when a job reference matches no stored job."""

    def __init__(self, reference: str) -> None:
        self.reference = reference
        super().__init__(f"No job found for '{reference}'.")
