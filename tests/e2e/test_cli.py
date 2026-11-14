"""
End-to-end CLI tests.

Drive the real CLI (argument parsing, command dispatch, output, exit codes)
against a real config file and a temp SQLite database. The only fakes are
the job source (no network) and the clock (a predictable "now"), passed in
through main()'s `build` argument.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhunt.bootstrap import Application, build_application
from jobhunt.cli.main import main
from jobhunt.config.settings import Settings
from jobhunt.domain.job import Job

# Midday UTC, so the local date is the same in any US timezone.
NOW = datetime(2026, 11, 13, 17, 0, tzinfo=UTC)


class FakeJobSource:
    """Returns canned jobs per company; no network."""

    def __init__(self, jobs_by_company: dict[str, list[Job]]) -> None:
        self._jobs_by_company = jobs_by_company

    def fetch_jobs(self, company: str) -> list[Job]:
        return self._jobs_by_company.get(company, [])


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _job(external_id: str) -> Job:
    return Job.create(
        source="greenhouse",
        external_id=external_id,
        company="Acme",
        title="Engineer",
        url=f"https://example.com/{external_id}",
        location="Remote",
        posted_at=datetime.fromisoformat("2026-01-01T12:00:00-05:00"),
    )


def _builder(jobs: list[Job]) -> Callable[[Settings], Application]:
    source = FakeJobSource({"acme": jobs})

    def build(settings: Settings) -> Application:
        return build_application(settings, source=source, clock=FixedClock())

    return build


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    # A real config file pointing at a temp database, so tests never touch
    # the real config.yaml or data/ folder.
    database = (tmp_path / "jobs.db").as_posix()
    path = tmp_path / "config.yaml"
    path.write_text(f'companies:\n  - acme\ndatabase_path: "{database}"\n', encoding="utf-8")
    return path


def _cli(config_path: Path, jobs: list[Job], *args: str) -> int:
    return main(["--config", str(config_path), *args], build=_builder(jobs))


class TestRun:
    def test_reports_found_and_new(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _cli(config_path, [_job("1"), _job("2")], "run") == 0
        assert "Found 2 job(s); 2 new." in capsys.readouterr().out

    def test_second_run_reports_zero_new(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jobs = [_job("1")]
        _cli(config_path, jobs, "run")
        capsys.readouterr()  # clear the first run's output

        _cli(config_path, jobs, "run")

        assert "0 new." in capsys.readouterr().out


class TestList:
    def test_shows_short_id_status_and_posted_date(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")
        capsys.readouterr()

        _cli(config_path, [job], "list")

        out = capsys.readouterr().out
        assert job.id[:8] in out
        assert "[new]" in out
        assert "Engineer" in out
        assert "2026-01-01" in out

    def test_empty_when_nothing_stored(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _cli(config_path, [], "list")
        assert "No jobs stored yet." in capsys.readouterr().out


class TestApply:
    def test_marks_applied_with_link_and_date(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")

        exit_code = _cli(config_path, [job], "apply", job.id[:8], "--link", "https://x/status")
        capsys.readouterr()
        _cli(config_path, [job], "show", job.id[:8])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "applied" in out
        assert "2026-11-13" in out
        assert "https://x/status" in out

    def test_applying_twice_is_refused(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")
        _cli(config_path, [job], "apply", job.id[:8])
        capsys.readouterr()

        exit_code = _cli(config_path, [job], "apply", job.id[:8])

        assert exit_code == 1
        assert "Already applied" in capsys.readouterr().err

    def test_unknown_job_says_not_found(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _cli(config_path, [_job("1")], "run")
        capsys.readouterr()

        exit_code = _cli(config_path, [_job("1")], "apply", "zzzzzzzz")

        assert exit_code == 1
        assert "No job found" in capsys.readouterr().err


class TestUpdateAndNote:
    def test_update_needs_link_or_contact(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")
        capsys.readouterr()

        assert _cli(config_path, [job], "update", job.id[:8]) == 1
        assert "--link" in capsys.readouterr().err

    def test_update_saves_contact(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")
        _cli(config_path, [job], "update", job.id[:8], "--contact", "Dana")
        capsys.readouterr()

        _cli(config_path, [job], "show", job.id[:8])

        assert "Dana" in capsys.readouterr().out

    def test_note_is_shown_with_its_date(
        self, config_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        job = _job("1")
        _cli(config_path, [job], "run")
        _cli(config_path, [job], "note", job.id[:8], "Recruiter replied")
        capsys.readouterr()

        _cli(config_path, [job], "show", job.id[:8])

        out = capsys.readouterr().out
        assert "Recruiter replied" in out
        assert "2026-11-13" in out
