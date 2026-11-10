"""
Fetch jobs use case.

Coordinates the steps of one "collect openings" run: ask each source for a
company's jobs, save what's new, and isolate any single company's failure
so the rest still complete. Depends only on the JobSource and JobRepository
ports — never on Greenhouse or SQLite directly — so it runs in tests
against fakes with no network or database.

It returns a FetchResult (structured data) rather than printing anything.
Presentation is the CLI's job; keeping output out of here is what lets the
same use case feed the console today and Discord or a web view later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jobhunt.domain.errors import JobSourceError
from jobhunt.domain.job import Job
from jobhunt.ports.job_repository import JobRepository
from jobhunt.ports.job_source import JobSource


@dataclass(frozen=True)
class CompanyFailure:
    """Records that one company could not be fetched, and why."""

    company: str
    reason: str


@dataclass(frozen=True)
class FetchResult:
    """
    The outcome of one fetch run, as data for a caller to render however it
    likes. Separates the three things a caller cares about: how much was
    found, how much was genuinely new (dedup), and what went wrong.
    """

    total_found: int = 0
    new_jobs: int = 0
    failures: list[CompanyFailure] = field(default_factory=list)


class FetchJobsService:
    def __init__(self, source: JobSource, repository: JobRepository) -> None:
        self._source = source
        self._repository = repository

    def fetch(self, companies: list[str]) -> FetchResult:
        """
        Fetch openings for each company, save new ones, and report the
        outcome.

        A failure fetching one company is caught and recorded, not raised,
        so the remaining companies still run — satisfying "one company's
        page is unavailable; the others still load and I'm told which
        failed." Jobs from all successful companies are saved together, and
        the repository's own de-duplication determines new_jobs.
        """
        collected: list[Job] = []
        failures: list[CompanyFailure] = []

        for company in companies:
            try:
                collected.extend(self._source.fetch_jobs(company))
            except JobSourceError as exc:
                failures.append(CompanyFailure(company=company, reason=str(exc)))

        new_jobs = self._repository.save_jobs(collected)

        return FetchResult(
            total_found=len(collected),
            new_jobs=new_jobs,
            failures=failures,
        )
