"""
Greenhouse job source adapter.

Implements the JobSource port against Greenhouse's public Job Board API
(https://boards-api.greenhouse.io). Read-only, no auth required. Turns
Greenhouse's one-company-per-call endpoint into our Job list, translating
any HTTP failure into a domain JobSourceError so the caller can isolate a
single company's failure from the rest of the run.
"""

from __future__ import annotations

import httpx

from jobhunt.adapters.sources import _parsing
from jobhunt.domain.errors import JobSourceError
from jobhunt.domain.job import Job
from jobhunt.ports.http_client import HttpClient

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseJobSource:
    """Fetches current openings for a company from its Greenhouse board."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def fetch_jobs(self, company: str) -> list[Job]:
        """
        Fetch all current openings for one company.

        `company` is the Greenhouse board token (the slug in the board URL,
        e.g. "stripe"). Raises JobSourceError if the board can't be reached
        or returns an error, so one bad company doesn't stop the others.
        """
        url = f"{_BASE_URL}/{company}/jobs"
        try:
            payload = self._http.get_json(url)
        except httpx.HTTPError as exc:
            raise JobSourceError(company, f"request failed: {exc}") from exc

        if not isinstance(payload, dict):
            raise JobSourceError(company, "unexpected response shape (expected an object)")

        return _parsing.parse_jobs(company, payload)
