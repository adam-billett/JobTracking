"""
Shared HTTP client.

One place for the cross-cutting concerns every source adapter needs:
sensible timeouts, retries on transient failures, and a consistent user
agent. Source adapters depend on this rather than importing httpx
directly, so retry/timeout policy is set once and changed once.
"""

from __future__ import annotations

import httpx

_DEFAULT_TIMEOUT_SECONDS = 10.0
_DEFAULT_MAX_RETRIES = 3
_USER_AGENT = "jobhunt/0.1 (personal job search tool)"


class HttpxClient:
    """
    A thin wrapper over httpx with timeouts, retries, and a user agent
    applied. Wraps GET only for now — that's all the public job board APIs
    need (they're read-only).
    """

    def __init__(
        self,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        # httpx's transport-level retries cover transient connection
        # errors (DNS blips, refused connections) without us hand-rolling a
        # retry loop. Status-code retries (e.g. 503) are handled by callers
        # that care, since "retry on 503" isn't universally correct.
        transport = httpx.HTTPTransport(retries=max_retries)
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    def get_json(self, url: str) -> object:
        """
        GET a URL and return the parsed JSON body. Raises httpx.HTTPError
        (or a subclass) on connection failure, timeout, or a non-2xx
        status — the caller translates that into a domain error.
        """
        response = self._client.get(url)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
