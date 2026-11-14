"""Unit tests for JobApplication."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobhunt.domain.errors import (
    AlreadyAppliedError,
    EmptyNoteError,
    InvalidStatusTransitionError,
)
from jobhunt.domain.job_application import JobApplication, Note
from jobhunt.domain.status import JobStatus

APPLIED_AT = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)


class TestMarkApplied:
    def test_sets_status_and_date(self) -> None:
        result = JobApplication("job-1").mark_applied(APPLIED_AT)
        assert result.status is JobStatus.APPLIED
        assert result.applied_at == APPLIED_AT

    def test_saves_link_and_contact_when_given(self) -> None:
        result = JobApplication("job-1").mark_applied(
            APPLIED_AT, tracking_url="https://x/status", contact="Dana"
        )
        assert result.tracking_url == "https://x/status"
        assert result.contact == "Dana"

    def test_keeps_earlier_contact_when_none_given(self) -> None:
        start = JobApplication("job-1", contact="Dana")
        assert start.mark_applied(APPLIED_AT).contact == "Dana"

    def test_already_applied_raises_with_original_date(self) -> None:
        applied = JobApplication("job-1").mark_applied(APPLIED_AT)
        with pytest.raises(AlreadyAppliedError) as exc_info:
            applied.mark_applied(LATER)
        assert exc_info.value.applied_at == APPLIED_AT
        assert "2026-11-13" in str(exc_info.value)

    def test_disallowed_status_raises(self) -> None:
        with pytest.raises(InvalidStatusTransitionError):
            JobApplication("job-1", status=JobStatus.REJECTED).mark_applied(APPLIED_AT)

    def test_does_not_change_the_original(self) -> None:
        original = JobApplication("job-1")
        original.mark_applied(APPLIED_AT)
        assert original.status is JobStatus.NEW


class TestUpdateDetails:
    def test_sets_link(self) -> None:
        result = JobApplication("job-1").update_details(tracking_url="https://x/status")
        assert result.tracking_url == "https://x/status"

    def test_leaves_fields_not_given(self) -> None:
        start = JobApplication("job-1", tracking_url="https://x/old", contact="Dana")
        result = start.update_details(tracking_url="https://x/new")
        assert result.tracking_url == "https://x/new"
        assert result.contact == "Dana"


class TestAddNote:
    def test_appends_notes_in_order_with_dates(self) -> None:
        result = (
            JobApplication("job-1")
            .add_note(APPLIED_AT, "Sent resume")
            .add_note(LATER, "Recruiter replied")
        )
        assert result.notes == (
            Note(created_at=APPLIED_AT, body="Sent resume"),
            Note(created_at=LATER, body="Recruiter replied"),
        )

    def test_strips_surrounding_whitespace(self) -> None:
        result = JobApplication("job-1").add_note(APPLIED_AT, "  Sent resume  ")
        assert result.notes[0].body == "Sent resume"

    @pytest.mark.parametrize("body", ["", "   "])
    def test_blank_note_raises(self, body: str) -> None:
        with pytest.raises(EmptyNoteError):
            JobApplication("job-1").add_note(APPLIED_AT, body)
