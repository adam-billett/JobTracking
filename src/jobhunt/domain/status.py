"""
Job status and the rules for moving between statuses.

The full status list comes from ARCHITECTURE.md §5, so the vocabulary is
fixed now. Only the transitions that a built story uses are allowed; each
later story (recommending, interviewing, rejecting...) adds its own moves
here. Anything not listed is refused.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    # Values are what the database stores, so they must never be renamed.
    NEW = "new"
    RECOMMENDED = "recommended"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    SKIPPED = "skipped"


_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    # JT-2: you can apply to a job you found or one that was recommended.
    JobStatus.NEW: frozenset({JobStatus.APPLIED}),
    JobStatus.RECOMMENDED: frozenset({JobStatus.APPLIED}),
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    """Return True if a job may move from `current` to `target`."""
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())
