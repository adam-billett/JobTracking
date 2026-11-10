"""
End-to-end CLI tests.

Drives the real CLI (argument parsing, command dispatch, output) against a
fixture source and a temp SQLite database — no network. Uses the
build_application source seam to inject a fake Greenhouse, so these verify
the whole wired path from `jobhunt run`/`list` down to storage and back.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from jobhunt.bootstrap import build_application
from jobhunt.cli import main as cli_main
from jobhunt.config.settings import Settings
from jobhunt.domain.job import Job


class FakeJobSource:
    """Returns canned jobs per company; no network."""

    def __init__(self, jobs_by_company: dict[str, list[Job]]) -> None:
        self._jobs_by_company = jobs_by_company

    def fetch_jobs(self, company: str) -> list[Job]:
        return self._jobs_by_company.get(company, [])


def _job(external_id: str) -> Job:
    return Job.create(
        source="greenhouse",
        external_id=external_id,
        company="Acme",
        title="Engineer",
        url=f"https://example.com/{external_id}",
        location="Remote",
        posted_at=datetime.fromisoformat("2026-01-01T00:00:00-05:00"),
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # tmp_path is pytest's per-test temp dir — the DB is created there and
    # cleaned up automatically, so tests never touch the real data/ folder.
    return Settings(companies=["acme"], database_path=str(tmp_path / "jobs.db"))


def _patch_source(monkeypatch: pytest.MonkeyPatch, source: FakeJobSource) -> None:
    # Make the CLI's build_application use our fake source. We wrap the real
    # function, injecting the fake, so the rest of the wiring stays real.
    original = build_application

    def _build_with_fake(settings: Settings, source_override=None):  # type: ignore[no-untyped-def]
        return original(settings, source=source)

    monkeypatch.setattr(cli_main, "build_application", _build_with_fake)


class TestRunCommand:
    def test_run_reports_found_and_new(
        self,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_source(monkeypatch, FakeJobSource({"acme": [_job("1"), _job("2")]}))
        monkeypatch.setattr(cli_main, "load_settings", lambda _path: settings)

        exit_code = cli_main.main(["run"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Found 2 job(s); 2 new." in out

    def test_second_run_reports_zero_new(
        self,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_source(monkeypatch, FakeJobSource({"acme": [_job("1")]}))
        monkeypatch.setattr(cli_main, "load_settings", lambda _path: settings)

        cli_main.main(["run"])
        capsys.readouterr()  # clear first run's output
        cli_main.main(["run"])

        assert "0 new." in capsys.readouterr().out


class TestListCommand:
    def test_list_shows_stored_jobs(
        self,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_source(monkeypatch, FakeJobSource({"acme": [_job("1")]}))
        monkeypatch.setattr(cli_main, "load_settings", lambda _path: settings)

        cli_main.main(["run"])
        capsys.readouterr()
        cli_main.main(["list"])

        out = capsys.readouterr().out
        assert "Engineer" in out
        assert "2026-01-01" in out

    def test_list_empty_when_nothing_stored(
        self,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(cli_main, "load_settings", lambda _path: settings)

        cli_main.main(["list"])

        assert "No jobs stored yet." in capsys.readouterr().out
