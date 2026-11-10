"""
Greenhouse JSON parsing helpers.

Private to the sources package (leading underscore). Isolated from the
adapter so the "turn Greenhouse's JSON into our Job" logic can be unit
tested directly against recorded fixtures, separate from any HTTP
concern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jobhunt.domain.job import Job

_SOURCE = "greenhouse"


def parse_jobs(company: str, payload: dict[str, Any]) -> list[Job]:
    """
    Translate a Greenhouse board's /jobs response into Job objects.

    `company` is used as the Job.company label. Greenhouse nests the list
    under a top-level "jobs" key; a missing or empty key yields no jobs
    rather than an error, since "this company currently has no openings"
    is a valid result, not a failure.
    """
    raw_jobs = payload.get("jobs", [])
    return [_parse_one(company, raw) for raw in raw_jobs]


def _parse_one(company: str, raw: dict[str, Any]) -> Job:
    return Job.create(
        source=_SOURCE,
        external_id=str(raw["id"]),
        company=_parse_company_name(company, raw),
        title=raw["title"],
        url=raw["absolute_url"],
        location=_parse_location(raw),
        posted_at=_parse_posted_at(raw),
    )


def _parse_company_name(company: str, raw: dict[str, Any]) -> str:
    # Greenhouse returns a display name ("Anthropic"); prefer it over the
    # board token ("anthropic"). Fall back to the token if it's absent.
    name = raw.get("company_name")
    return name if isinstance(name, str) and name else company


def _parse_location(raw: dict[str, Any]) -> str | None:
    location = raw.get("location")
    if isinstance(location, dict):
        name = location.get("name")
        return name if isinstance(name, str) else None
    return None


def _parse_posted_at(raw: dict[str, Any]) -> datetime | None:
    # Prefer first_published (when the posting went live); fall back to
    # updated_at. Both are ISO 8601 with offset in Greenhouse's responses.
    raw_date = raw.get("first_published") or raw.get("updated_at")
    if not isinstance(raw_date, str):
        return None
    try:
        return datetime.fromisoformat(raw_date)
    except ValueError:
        return None
