"""
Core domain model: a job posting as our system understands it.

Provider-agnostic — it knows nothing about Greenhouse, HTTP, or SQLite.
Adapters translate their raw data into this shape; everything above the
adapters speaks only in these terms, so a second source (Lever, Ashby)
slots in later without changing anything here.

Scope note: this carries the "posting" facts collected in JT-1 only.
Tracking state (status, applied_at, ...) and rating (fit_score, ...) from
the §5 data model belong to later stories and their own migrations; they
are deliberately NOT on this model yet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


def make_job_id(source: str, external_id: str) -> str:
    """
    Stable identity for a posting: a hash of source + external_id.

    Using a derived hash (not the database row id) means the same posting
    seen on two runs resolves to the same id, which is what makes
    de-duplication work regardless of where or when it was stored. The
    source is included so two providers that happen to reuse the same
    external_id never collide.
    """
    return hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()


@dataclass(frozen=True)
class Job:
    """A single job posting collected from a source."""

    id: str  # hash of source + external_id (see make_job_id)
    source: str  # which provider this came from, e.g. "greenhouse"
    external_id: str  # the provider's own id for this posting
    company: str
    title: str
    url: str  # link to the original posting
    location: str | None
    posted_at: datetime | None

    @classmethod
    def create(
        cls,
        *,
        source: str,
        external_id: str,
        company: str,
        title: str,
        url: str,
        location: str | None,
        posted_at: datetime | None,
    ) -> Job:
        """
        Build a Job, deriving its id from source + external_id so callers
        never construct an inconsistent id by hand. Keyword-only to keep
        call sites readable given the number of string fields.
        """
        return cls(
            id=make_job_id(source, external_id),
            source=source,
            external_id=external_id,
            company=company,
            title=title,
            url=url,
            location=location,
            posted_at=posted_at,
        )
