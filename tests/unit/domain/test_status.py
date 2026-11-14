"""Unit tests for job status transitions."""

from __future__ import annotations

import pytest

from jobhunt.domain.status import JobStatus, can_transition


class TestCanTransition:
    @pytest.mark.parametrize("start", [JobStatus.NEW, JobStatus.RECOMMENDED])
    def test_can_apply_from_new_or_recommended(self, start: JobStatus) -> None:
        assert can_transition(start, JobStatus.APPLIED)

    @pytest.mark.parametrize(
        "start", [JobStatus.APPLIED, JobStatus.REJECTED, JobStatus.SKIPPED, JobStatus.OFFER]
    )
    def test_cannot_apply_from_other_statuses(self, start: JobStatus) -> None:
        assert not can_transition(start, JobStatus.APPLIED)

    def test_unlisted_transition_is_refused(self) -> None:
        assert not can_transition(JobStatus.NEW, JobStatus.OFFER)


class TestStoredValues:
    def test_values_match_what_the_database_stores(self) -> None:
        # Renaming a value would orphan every row already stored with it.
        assert JobStatus.NEW.value == "new"
        assert JobStatus.APPLIED.value == "applied"
