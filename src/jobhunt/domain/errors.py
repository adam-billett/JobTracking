"""
Domain error types.

Defining our own errors (rather than leaking requests.HTTPError or
sqlite3.Error upward) keeps the application layer independent of which
adapter raised the problem. A failure fetching one company is an
expected, recoverable condition — not a crash — so it gets its own type
the use case can catch and report per-company.
"""

from __future__ import annotations


class JobHuntError(Exception):
    """Base class for all errors this application raises deliberately."""


class JobSourceError(JobHuntError):
    """
    Raised when a job source fails to return usable data for one company
    (network failure, unexpected response, company not found). Carries the
    company identifier so the caller can report which one failed while
    continuing with the others.
    """

    def __init__(self, company: str, message: str):
        self.company = company
        super().__init__(f"[{company}] {message}")
