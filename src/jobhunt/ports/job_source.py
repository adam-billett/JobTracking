"""
JobSource port.

The contract any job provider must satisfy. GreenhouseJobSource is the
first implementation; future sources (Lever, Ashby, ...) implement this
same interface, so the application layer never learns which provider it's
talking to.
"""

from __future__ import annotations

from typing import Protocol

from jobhunt.domain.job import Job


class JobSource(Protocol):
    def fetch_jobs(self, company: str) -> list[Job]:
        """
        Return the current open postings for one company.

        `company` is the source-specific identifier (for Greenhouse, the
        board token / slug, e.g. "stripe"). Raises JobSourceError if the
        company's jobs cannot be retrieved, so the caller can isolate the
        failure to this one company.
        """
        ...
