"""
Unit tests for FetchJobsService.

No Greenhouse, no SQLite — a fake source and the real in-memory repository
(trusted because the contract suite proves it matches SQLite). This is
where the JT-1 acceptance criteria are verified: dedup reporting across
runs, and one company failing without stopping the others.
"""

from __future__ import annotations

from datetime import datetime

from jobhunt.adapters.storage.memory_repository import InMemoryJobRepository
from jobhunt.application.fetch_jobs import FetchJobsService
from jobhunt.domain.errors import JobSourceError
from jobhunt.domain.job import Job


class FakeJobSource:
    """
    Returns canned jobs per company, or raises JobSourceError for companies
    configured to fail. Lets each test script exactly the scenario it needs.
    """

    def __init__(
        self,
        jobs_by_company: dict[str, list[Job]] | None = None,
        failing: set[str] | None = None,
    ) -> None:
        self._jobs_by_company = jobs_by_company or {}
        self._failing = failing or set()

    def fetch_jobs(self, company: str) -> list[Job]:
        if company in self._failing:
            raise JobSourceError(company, "simulated failure")
        return self._jobs_by_company.get(company, [])


def _job(external_id: str, company: str = "Acme") -> Job:
    return Job.create(
        source="greenhouse",
        external_id=external_id,
        company=company,
        title="Engineer",
        url=f"https://example.com/{external_id}",
        location="Remote",
        posted_at=datetime.fromisoformat("2026-01-01T00:00:00-05:00"),
    )


class TestFetch:
    def test_collects_jobs_from_all_companies(self) -> None:
        source = FakeJobSource({"acme": [_job("1")], "globex": [_job("2")]})
        service = FetchJobsService(source, InMemoryJobRepository())

        result = service.fetch(["acme", "globex"])

        assert result.total_found == 2
        assert result.new_jobs == 2
        assert result.failures == []

    def test_saves_jobs_to_repository(self) -> None:
        repository = InMemoryJobRepository()
        source = FakeJobSource({"acme": [_job("1")]})
        FetchJobsService(source, repository).fetch(["acme"])

        assert len(repository.list_jobs()) == 1


class TestDeduplicationAcrossRuns:
    def test_second_run_reports_no_new_jobs(self) -> None:
        repository = InMemoryJobRepository()
        source = FakeJobSource({"acme": [_job("1"), _job("2")]})
        service = FetchJobsService(source, repository)

        first = service.fetch(["acme"])
        second = service.fetch(["acme"])

        assert first.new_jobs == 2
        assert second.new_jobs == 0
        assert len(repository.list_jobs()) == 2  # no duplicates created


class TestFailureIsolation:
    def test_one_company_failing_does_not_stop_others(self) -> None:
        source = FakeJobSource(
            jobs_by_company={"good": [_job("1")]},
            failing={"bad"},
        )
        service = FetchJobsService(source, InMemoryJobRepository())

        result = service.fetch(["bad", "good"])

        # The good company's jobs still came through...
        assert result.total_found == 1
        assert result.new_jobs == 1
        # ...and the failure is reported, naming which company.
        assert len(result.failures) == 1
        assert result.failures[0].company == "bad"

    def test_all_companies_failing_reports_all(self) -> None:
        source = FakeJobSource(failing={"a", "b"})
        service = FetchJobsService(source, InMemoryJobRepository())

        result = service.fetch(["a", "b"])

        assert result.total_found == 0
        assert result.new_jobs == 0
        assert {f.company for f in result.failures} == {"a", "b"}
