"""
Contract tests for JobRepository.

One shared suite that EVERY JobRepository implementation must pass. The
`repository` fixture is parametrized over both implementations, so each
test below runs twice — once against in-memory, once against SQLite. This
guarantees the fast fake used elsewhere in tests behaves identically to
the real database.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from jobhunt.adapters.storage.memory_repository import InMemoryJobRepository
from jobhunt.adapters.storage.sqlite.database import connect
from jobhunt.adapters.storage.sqlite.repository import SqliteJobRepository
from jobhunt.domain.errors import JobNotFoundError
from jobhunt.domain.job import Job
from jobhunt.domain.job_application import JobApplication, Note
from jobhunt.domain.status import JobStatus
from jobhunt.ports.job_repository import JobRepository


@pytest.fixture(params=["memory", "sqlite"])
def repository(request: pytest.FixtureRequest) -> Iterator[JobRepository]:
    if request.param == "memory":
        yield InMemoryJobRepository()
    else:
        connection = connect(":memory:")
        try:
            yield SqliteJobRepository(connection)
        finally:
            connection.close()


def _job(external_id: str, title: str = "Engineer") -> Job:
    return Job.create(
        source="greenhouse",
        external_id=external_id,
        company="Acme",
        title=title,
        url=f"https://example.com/{external_id}",
        location="Remote",
        posted_at=datetime.fromisoformat("2026-01-01T00:00:00-05:00"),
    )


class TestSaveAndList:
    def test_saved_jobs_are_listed(self, repository: JobRepository) -> None:
        repository.save_jobs([_job("1"), _job("2")])
        listed = repository.list_jobs()
        assert {j.external_id for j in listed} == {"1", "2"}

    def test_list_is_empty_initially(self, repository: JobRepository) -> None:
        assert repository.list_jobs() == []

    def test_save_returns_count_of_new_jobs(self, repository: JobRepository) -> None:
        assert repository.save_jobs([_job("1"), _job("2")]) == 2


class TestDeduplication:
    def test_saving_same_job_twice_does_not_duplicate(self, repository: JobRepository) -> None:
        repository.save_jobs([_job("1")])
        repository.save_jobs([_job("1")])
        assert len(repository.list_jobs()) == 1

    def test_second_save_reports_zero_new(self, repository: JobRepository) -> None:
        repository.save_jobs([_job("1")])
        assert repository.save_jobs([_job("1")]) == 0

    def test_mixed_new_and_existing_counts_only_new(self, repository: JobRepository) -> None:
        repository.save_jobs([_job("1")])
        inserted = repository.save_jobs([_job("1"), _job("2")])  # 1 exists, 2 is new
        assert inserted == 1
        assert len(repository.list_jobs()) == 2


class TestRoundTrip:
    def test_job_fields_survive_save_and_load(self, repository: JobRepository) -> None:
        original = _job("1", title="Staff Engineer")
        repository.save_jobs([original])
        loaded = repository.list_jobs()[0]
        assert loaded == original  # frozen dataclass equality checks every field


APPLIED_AT = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)


class TestGetJob:
    def test_returns_stored_job(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job])
        assert repository.get_job(job.id) == job

    def test_unknown_id_returns_none(self, repository: JobRepository) -> None:
        assert repository.get_job("missing") is None


class TestFindJobIds:
    def test_prefix_matches_job(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job, _job("2")])
        assert job.id in repository.find_job_ids(job.id[:8])

    def test_full_id_matches_exactly_one(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job, _job("2")])
        assert repository.find_job_ids(job.id) == [job.id]

    def test_unmatched_prefix_returns_empty(self, repository: JobRepository) -> None:
        repository.save_jobs([_job("1")])
        assert repository.find_job_ids("zzzz") == []

    def test_wildcard_characters_match_literally(self, repository: JobRepository) -> None:
        # "%" would match everything under SQL LIKE; it must match nothing.
        repository.save_jobs([_job("1")])
        assert repository.find_job_ids("%") == []


class TestApplications:
    def test_untracked_job_has_default_application(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job])
        assert repository.get_application(job.id) == JobApplication(job.id)

    def test_unknown_job_has_no_application(self, repository: JobRepository) -> None:
        assert repository.get_application("missing") is None

    def test_saved_application_round_trips(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job])
        application = (
            JobApplication(job.id)
            .mark_applied(APPLIED_AT, tracking_url="https://x/status", contact="Dana")
            .add_note(APPLIED_AT, "Sent resume")
            .add_note(LATER, "Recruiter replied")
        )

        repository.save_application(application)

        assert repository.get_application(job.id) == application

    def test_resaving_keeps_each_note_once(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job])
        first = JobApplication(job.id).add_note(APPLIED_AT, "Sent resume")
        repository.save_application(first)

        repository.save_application(first.add_note(LATER, "Recruiter replied"))

        loaded = repository.get_application(job.id)
        assert loaded is not None
        assert loaded.notes == (
            Note(created_at=APPLIED_AT, body="Sent resume"),
            Note(created_at=LATER, body="Recruiter replied"),
        )

    def test_saving_for_unknown_job_raises(self, repository: JobRepository) -> None:
        with pytest.raises(JobNotFoundError):
            repository.save_application(JobApplication("missing"))

    def test_tracking_does_not_change_job_listing(self, repository: JobRepository) -> None:
        job = _job("1")
        repository.save_jobs([job])
        repository.save_application(JobApplication(job.id).mark_applied(APPLIED_AT))
        assert repository.list_jobs() == [job]
        assert repository.get_application(job.id).status is JobStatus.APPLIED  # type: ignore[union-attr]
