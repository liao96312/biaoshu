from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int


class FixedWindowRateLimiter:
    def __init__(self, limit: int = 100, window_seconds: int = 3600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[int, int]] = {}

    def check(self, key: str) -> RateLimitResult:
        now = int(time.time())
        window_start = now - (now % self.window_seconds)
        count, start = self._buckets.get(key, (0, window_start))
        if start != window_start:
            count = 0
            start = window_start
        count += 1
        self._buckets[key] = (count, start)
        remaining = max(self.limit - count, 0)
        return RateLimitResult(
            allowed=count <= self.limit,
            limit=self.limit,
            remaining=remaining,
            reset=start + self.window_seconds,
        )


rate_limiter = FixedWindowRateLimiter()
