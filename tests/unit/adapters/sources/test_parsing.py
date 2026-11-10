"""
Unit tests for Greenhouse JSON parsing.

Tested directly against a recorded fixture (real Greenhouse shape) plus
small hand-built payloads for edge cases. No HTTP here — parsing is pure
and deserves its own fast, focused tests separate from the adapter.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jobhunt.adapters.sources import _parsing
from jobhunt.domain.job import make_job_id

_FIXTURE = Path(__file__).parents[3] / "fixtures" / "sources" / "greenhouse" / "anthropic_jobs.json"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


class TestParseJobsFixture:
    def test_parses_all_jobs_from_fixture(self) -> None:
        payload = _load_fixture()
        jobs = _parsing.parse_jobs("anthropic", payload)
        assert len(jobs) == len(payload["jobs"])

    def test_first_job_fields_map_correctly(self) -> None:
        payload = _load_fixture()
        first_raw = payload["jobs"][0]
        job = _parsing.parse_jobs("anthropic", payload)[0]

        assert job.source == "greenhouse"
        assert job.external_id == str(first_raw["id"])
        assert job.title == first_raw["title"]
        assert job.url == first_raw["absolute_url"]
        # Greenhouse's display name is preferred over the board token.
        assert job.company == first_raw["company_name"]

    def test_id_is_hash_of_source_and_external_id(self) -> None:
        payload = _load_fixture()
        job = _parsing.parse_jobs("anthropic", payload)[0]
        assert job.id == make_job_id("greenhouse", job.external_id)


class TestParseEdgeCases:
    def test_empty_jobs_key_yields_no_jobs(self) -> None:
        assert _parsing.parse_jobs("acme", {"jobs": []}) == []

    def test_missing_jobs_key_yields_no_jobs(self) -> None:
        # "no openings" is a valid result, not an error.
        assert _parsing.parse_jobs("acme", {}) == []

    def test_missing_location_is_none(self) -> None:
        payload = {"jobs": [_minimal_raw(location=None)]}
        job = _parsing.parse_jobs("acme", payload)[0]
        assert job.location is None

    def test_location_without_name_is_none(self) -> None:
        payload = {"jobs": [_minimal_raw(location={})]}
        job = _parsing.parse_jobs("acme", payload)[0]
        assert job.location is None

    def test_prefers_first_published_over_updated_at(self) -> None:
        raw = _minimal_raw()
        raw["first_published"] = "2024-12-20T13:53:38-05:00"
        raw["updated_at"] = "2026-08-21T21:32:54-04:00"
        job = _parsing.parse_jobs("acme", {"jobs": [raw]})[0]
        assert job.posted_at == datetime.fromisoformat("2024-12-20T13:53:38-05:00")

    def test_falls_back_to_updated_at_when_no_first_published(self) -> None:
        raw = _minimal_raw()
        raw.pop("first_published", None)
        raw["updated_at"] = "2026-08-21T21:32:54-04:00"
        job = _parsing.parse_jobs("acme", {"jobs": [raw]})[0]
        assert job.posted_at == datetime.fromisoformat("2026-08-21T21:32:54-04:00")

    def test_unparseable_date_is_none(self) -> None:
        raw = _minimal_raw()
        raw["first_published"] = "not-a-date"
        raw["updated_at"] = "also-bad"
        job = _parsing.parse_jobs("acme", {"jobs": [raw]})[0]
        assert job.posted_at is None

    def test_company_name_falls_back_to_token(self) -> None:
        raw = _minimal_raw()
        raw.pop("company_name", None)
        job = _parsing.parse_jobs("acme", {"jobs": [raw]})[0]
        assert job.company == "acme"


def _minimal_raw(location: dict[str, Any] | None = None) -> dict[str, Any]:
    """A minimal valid Greenhouse job object for edge-case tests."""
    return {
        "id": 123,
        "title": "Engineer",
        "absolute_url": "https://example.com/jobs/123",
        "company_name": "Acme",
        "location": location,
        "first_published": "2026-01-01T00:00:00-05:00",
        "updated_at": "2026-01-02T00:00:00-05:00",
    }
