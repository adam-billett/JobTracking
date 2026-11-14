"""
Unit tests for TrackApplicationService.

A fixed clock pins "now", and the in-memory repository stands in for SQLite
(the contract suite proves they behave the same). This is where JT-2's
acceptance criteria are verified.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import pytest

from jobhunt.adapters.storage.memory_repository import InMemoryJobRepository
from jobhunt.application.track_application import TrackApplicationService
from jobhunt.domain.errors import (
    AlreadyAppliedError,
    AmbiguousJobReferenceError,
    JobNotFoundError,
)
from jobhunt.domain.job import Job
from jobhunt.domain.status import JobStatus

NOW = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _job(external_id: str) -> Job:
    return Job.create(
        source="greenhouse",
        external_id=external_id,
        company="Acme",
        title=f"Engineer {external_id}",
        url=f"https://example.com/{external_id}",
        location="Remote",
        posted_at=None,
    )


def _service(*jobs: Job) -> tuple[TrackApplicationService, InMemoryJobRepository]:
    repository = InMemoryJobRepository()
    repository.save_jobs(list(jobs))
    return TrackApplicationService(repository, FixedClock(NOW)), repository


class TestApply:
    def test_records_status_and_todays_date(self) -> None:
        job = _job("1")
        service, repository = _service(job)

        service.apply(job.id[:8])

        stored = repository.get_application(job.id)
        assert stored is not None
        assert stored.status is JobStatus.APPLIED
        assert stored.applied_at == NOW

    def test_saves_link_and_contact(self) -> None:
        job = _job("1")
        service, repository = _service(job)

        service.apply(job.id[:8], tracking_url="https://x/status", contact="Dana")

        stored = repository.get_application(job.id)
        assert stored is not None
        assert stored.tracking_url == "https://x/status"
        assert stored.contact == "Dana"

    def test_applying_twice_keeps_original_record(self) -> None:
        job = _job("1")
        service, repository = _service(job)
        service.apply(job.id[:8], tracking_url="https://x/first")

        with pytest.raises(AlreadyAppliedError):
            service.apply(job.id[:8], tracking_url="https://x/second")

        stored = repository.get_application(job.id)
        assert stored is not None
        assert stored.tracking_url == "https://x/first"


class TestReferences:
    def test_reference_is_case_and_space_insensitive(self) -> None:
        job = _job("1")
        service, _ = _service(job)
        assert service.show(f"  {job.id[:8].upper()} ").job == job

    def test_full_id_works(self) -> None:
        job = _job("1")
        service, _ = _service(job)
        assert service.show(job.id).job == job

    def test_unknown_reference_raises_not_found(self) -> None:
        service, _ = _service(_job("1"))
        with pytest.raises(JobNotFoundError):
            service.show("zzzzzzzz")

    def test_blank_reference_raises_not_found(self) -> None:
        service, _ = _service(_job("1"))
        with pytest.raises(JobNotFoundError):
            service.show("   ")

    def test_shared_prefix_raises_ambiguous(self) -> None:
        # 17 ids over 16 possible first hex characters: at least two must
        # share one, so this finds a real ambiguous prefix every time.
        jobs = [_job(str(n)) for n in range(17)]
        service, _ = _service(*jobs)
        by_first_char: dict[str, list[str]] = defaultdict(list)
        for job in jobs:
            by_first_char[job.id[0]].append(job.id)
        shared = next(char for char, ids in by_first_char.items() if len(ids) > 1)

        with pytest.raises(AmbiguousJobReferenceError):
            service.show(shared)


class TestDetailsAndNotes:
    def test_update_details_saves_link_without_applying(self) -> None:
        job = _job("1")
        service, repository = _service(job)

        service.update_details(job.id[:8], tracking_url="https://x/status")

        stored = repository.get_application(job.id)
        assert stored is not None
        assert stored.tracking_url == "https://x/status"
        assert stored.status is JobStatus.NEW

    def test_add_note_is_dated_now(self) -> None:
        job = _job("1")
        service, repository = _service(job)

        service.add_note(job.id[:8], "Sent resume")

        stored = repository.get_application(job.id)
        assert stored is not None
        assert stored.notes[0].body == "Sent resume"
        assert stored.notes[0].created_at == NOW

    def test_note_on_unknown_job_raises_not_found(self) -> None:
        service, _ = _service(_job("1"))
        with pytest.raises(JobNotFoundError):
            service.add_note("zzzzzzzz", "Sent resume")


class TestListTracked:
    def test_lists_every_job_with_its_status(self) -> None:
        first, second = _job("1"), _job("2")
        service, _ = _service(first, second)
        service.apply(first.id[:8])

        statuses = {t.job.id: t.application.status for t in service.list_tracked()}

        assert statuses == {first.id: JobStatus.APPLIED, second.id: JobStatus.NEW}
