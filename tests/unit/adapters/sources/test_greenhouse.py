"""
Unit tests for the Greenhouse adapter.

A fake HttpClient stands in for the real one, so these run with no network
and deterministically. Verifies the adapter builds the right URL, returns
parsed jobs, and translates HTTP failures into JobSourceError so one
company's failure stays isolated.
"""

from __future__ import annotations

import httpx
import pytest

from jobhunt.adapters.sources.greenhouse import GreenhouseJobSource
from jobhunt.domain.errors import JobSourceError


class FakeHttpClient:
    """Returns a canned payload, or raises a canned error, and records the URL it was asked for."""

    def __init__(self, *, payload: object = None, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error
        self.requested_url: str | None = None

    def get_json(self, url: str) -> object:
        self.requested_url = url
        if self._error is not None:
            raise self._error
        return self._payload


class TestFetchJobs:
    def test_builds_correct_board_url(self) -> None:
        fake = FakeHttpClient(payload={"jobs": []})
        GreenhouseJobSource(fake).fetch_jobs("stripe")
        assert fake.requested_url == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs"

    def test_returns_parsed_jobs(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": 1,
                    "title": "Engineer",
                    "absolute_url": "https://example.com/1",
                    "company_name": "Stripe",
                    "location": {"name": "Remote"},
                    "first_published": "2026-01-01T00:00:00-05:00",
                    "updated_at": "2026-01-01T00:00:00-05:00",
                }
            ]
        }
        jobs = GreenhouseJobSource(FakeHttpClient(payload=payload)).fetch_jobs("stripe")
        assert len(jobs) == 1
        assert jobs[0].title == "Engineer"
        assert jobs[0].company == "Stripe"

    def test_http_error_becomes_job_source_error(self) -> None:
        fake = FakeHttpClient(error=httpx.ConnectError("boom"))
        with pytest.raises(JobSourceError) as exc_info:
            GreenhouseJobSource(fake).fetch_jobs("stripe")
        # The failing company is named, so the caller can report which one failed.
        assert exc_info.value.company == "stripe"

    def test_non_dict_payload_becomes_job_source_error(self) -> None:
        fake = FakeHttpClient(payload=["not", "a", "dict"])
        with pytest.raises(JobSourceError):
            GreenhouseJobSource(fake).fetch_jobs("stripe")
