"""
Clock port.

Reading the current time is an external dependency, same as the network
or the filesystem. Injecting it through this port (rather than calling
datetime.now() inline) lets tests pin "now" to a fixed value and assert
on it deterministically, instead of chasing a moving wall clock.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time (timezone-aware, UTC)."""
        ...
