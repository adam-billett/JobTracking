"""
Application tracking for one job: status, applied date, tracking link,
contact and dated notes.

Kept separate from Job on purpose. Job holds facts from the job board and
never changes; JobApplication holds my own workflow, which changes often.
Both are stored in the jobs table, but they have different reasons to
change, so they are different objects.

Every method returns a new JobApplication instead of changing this one, so
a failed step can never leave half-updated state behind.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from jobhunt.domain.errors import (
    AlreadyAppliedError,
    EmptyNoteError,
    InvalidStatusTransitionError,
)
from jobhunt.domain.status import JobStatus, can_transition


@dataclass(frozen=True)
class Note:
    """A free-text note, stamped with when it was added."""

    created_at: datetime
    body: str


@dataclass(frozen=True)
class JobApplication:
    """Where my application to one job stands."""

    job_id: str
    status: JobStatus = JobStatus.NEW
    applied_at: datetime | None = None
    tracking_url: str | None = None
    contact: str | None = None
    notes: tuple[Note, ...] = ()

    def mark_applied(
        self,
        at: datetime,
        *,
        tracking_url: str | None = None,
        contact: str | None = None,
    ) -> JobApplication:
        """
        Record that I applied at `at`, optionally with the tracking link and
        a contact. A link or contact saved earlier is kept unless a new one
        is given.
        """
        if self.status is JobStatus.APPLIED:
            raise AlreadyAppliedError(self.job_id, self.applied_at)
        if not can_transition(self.status, JobStatus.APPLIED):
            raise InvalidStatusTransitionError(self.status, JobStatus.APPLIED)

        return replace(
            self,
            status=JobStatus.APPLIED,
            applied_at=at,
            tracking_url=tracking_url if tracking_url is not None else self.tracking_url,
            contact=contact if contact is not None else self.contact,
        )

    def update_details(
        self,
        *,
        tracking_url: str | None = None,
        contact: str | None = None,
    ) -> JobApplication:
        """
        Set the tracking link and/or contact, leaving any field not given as
        it is. Allowed at any status: a recruiter's name is often known
        before applying, and a confirmation link often arrives after.
        """
        return replace(
            self,
            tracking_url=tracking_url if tracking_url is not None else self.tracking_url,
            contact=contact if contact is not None else self.contact,
        )

    def add_note(self, at: datetime, body: str) -> JobApplication:
        """Append a note. Notes are never edited or removed, only added."""
        text = body.strip()
        if not text:
            raise EmptyNoteError()
        return replace(self, notes=(*self.notes, Note(created_at=at, body=text)))
