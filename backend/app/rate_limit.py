"""Small in-process sliding-window rate limiter.

Limits are read from settings on every request, so tests and deploys can
change them without redecorating routes. A single Render free-tier instance
runs one process, which makes in-memory state correct; a multi-instance
deploy would replace this with a shared store such as Redis.
"""

import re
import time
from collections import deque
from threading import Lock

from fastapi import Depends, HTTPException, Request

_LIMIT_RE = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour|day)\s*$")
_WINDOWS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def parse_limit(spec: str) -> tuple[int, int]:
    match = _LIMIT_RE.match(spec or "")
    if not match:
        raise ValueError(f"Invalid rate limit spec: {spec!r}")
    return int(match.group(1)), _WINDOWS[match.group(2)]


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = {}
        self._lock = Lock()

    def check(self, key: str, spec: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        count, window = parse_limit(spec)
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= count:
                retry_after = max(1, int(hits[0] + window - now))
                return False, retry_after
            hits.append(now)
            return True, 0


def limit(scope: str):
    """FastAPI dependency factory: limit("login"), limit("mentor"), ..."""

    def _enforce(request: Request):
        settings = request.app.state.settings
        spec = getattr(settings, f"rate_limit_{scope}")
        limiter: RateLimiter = request.app.state.rate_limiter
        client = request.client.host if request.client else "unknown"
        allowed, retry_after = limiter.check(f"{scope}:{client}", spec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded ({spec}). "
                    f"Try again in {retry_after} seconds."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    return Depends(_enforce)
