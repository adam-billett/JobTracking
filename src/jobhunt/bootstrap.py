"""
Composition root.

The ONLY place concrete adapters are chosen and wired to use cases (per
ARCHITECTURE.md §3, rule 5). Everything else depends on ports. Swapping
SQLite for another store, or adding a second job source, is a change here
and nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobhunt.adapters.http.client import HttpxClient
from jobhunt.adapters.sources.greenhouse import GreenhouseJobSource
from jobhunt.adapters.storage.sqlite.database import connect
from jobhunt.adapters.storage.sqlite.repository import SqliteJobRepository
from jobhunt.application.fetch_jobs import FetchJobsService
from jobhunt.config.settings import Settings
from jobhunt.ports.job_source import JobSource


@dataclass(frozen=True)
class Application:
    """The wired-up application: use cases plus the settings they run with."""

    fetch_jobs: FetchJobsService
    repository: SqliteJobRepository
    settings: Settings


def build_application(settings: Settings, source: JobSource | None = None) -> Application:
    """
    Wire concrete adapters into the use cases and return them ready to run.

    `source` defaults to the real Greenhouse source; tests pass a fake to
    exercise the CLI end-to-end without hitting the network. This is the
    one seam the composition root exposes for that purpose.
    """
    if source is None:
        http = HttpxClient()
        source = GreenhouseJobSource(http)

    connection = connect(settings.database_path)
    repository = SqliteJobRepository(connection)

    return Application(
        fetch_jobs=FetchJobsService(source, repository),
        repository=repository,
        settings=settings,
    )
