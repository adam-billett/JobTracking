"""
Real clock: the adapter behind the Clock port.

Returns timezone-aware UTC so stored times compare correctly no matter
which timezone the laptop is set to. Tests use a fixed clock instead.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
