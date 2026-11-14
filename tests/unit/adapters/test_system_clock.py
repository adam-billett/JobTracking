"""Unit test for the real clock."""

from __future__ import annotations

from datetime import UTC

from jobhunt.adapters.system_clock import SystemClock


def test_returns_timezone_aware_utc() -> None:
    assert SystemClock().now().tzinfo is UTC
