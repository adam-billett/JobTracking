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
from jobhunt.adapters.system_clock import SystemClock
from jobhunt.application.fetch_jobs import FetchJobsService
from jobhunt.application.track_application import TrackApplicationService
from jobhunt.config.settings import Settings
from jobhunt.ports.clock import Clock
from jobhunt.ports.job_source import JobSource


@dataclass(frozen=True)
class Application:
    """The wired-up application: use cases plus the settings they run with."""

    fetch_jobs: FetchJobsService
    track: TrackApplicationService
    settings: Settings


def build_application(
    settings: Settings,
    *,
    source: JobSource | None = None,
    clock: Clock | None = None,
) -> Application:
    """
    Wire concrete adapters into the use cases and return them ready to run.

    `source` and `clock` default to the real ones; end-to-end tests pass a
    fake source and a fixed clock so they run without the network and with
    a predictable "now".
    """
    if source is None:
        source = GreenhouseJobSource(HttpxClient())
    if clock is None:
        clock = SystemClock()

    repository = SqliteJobRepository(connect(settings.database_path))

    return Application(
        fetch_jobs=FetchJobsService(source, repository),
        track=TrackApplicationService(repository, clock),
        settings=settings,
    )
