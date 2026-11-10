"""
HttpClient port.

The contract a source adapter needs from an HTTP client: fetch a URL and
return parsed JSON. Depending on this interface (rather than the concrete
HttpxClient) keeps the dependency pointing inward — adapters depend on
ports — and lets tests supply a fake client with no network.
"""

from __future__ import annotations

from typing import Protocol


class HttpClient(Protocol):
    def get_json(self, url: str) -> object:
        """GET a URL and return the parsed JSON body, or raise on failure."""
        ...
