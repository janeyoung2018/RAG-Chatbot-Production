"""Simple in-memory rate limiting utilities."""
from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic
from typing import Deque, DefaultDict

from fastapi import Depends, HTTPException, Request, status

from .config import get_settings
from .security import require_api_key


class RateLimiter:
    """Token bucket style limiter with sliding window semantics."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = max(limit, 1)
        self._window = max(window_seconds, 1)
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def allow(self, identity: str) -> bool:
        now = monotonic()
        bucket = self._hits[identity]
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return False
        bucket.append(now)
        return True


_limiter: RateLimiter | None = None


def _get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        settings = get_settings()
        _limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_window_seconds)
    return _limiter


async def enforce_rate_limit(
    request: Request,
    _: str | None = Depends(require_api_key),
) -> None:
    """Ensure the caller is within the configured rate limit."""
    limiter = _get_limiter()
    identity = None
    if request.headers.get("X-API-Key"):
        identity = request.headers["X-API-Key"]
    if identity is None and request.client:
        identity = request.client.host or "anonymous"
    identity = identity or "anonymous"
    if not limiter.allow(identity):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
