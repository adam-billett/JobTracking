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
from datetime import datetime

import pytest

from jobhunt.adapters.storage.memory_repository import InMemoryJobRepository
from jobhunt.adapters.storage.sqlite.database import connect
from jobhunt.adapters.storage.sqlite.repository import SqliteJobRepository
from jobhunt.domain.job import Job
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
