"""Async per-host token-bucket rate limiter for polite pacing.

Each host gets its own bucket. Tokens refill at ``rate`` per second up to
``burst`` capacity; :meth:`acquire` waits asynchronously until a token is free.
This honours crawl-delay-style politeness without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class _Bucket:
    rate: float
    capacity: float
    tokens: float
    updated: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RateLimiter:
    """Per-host token bucket.

    Args:
        rate: Steady-state requests per second per host.
        burst: Maximum burst (bucket capacity). Defaults to ``ceil(rate)``.
        time_func: Monotonic clock (overridable for tests).
        sleep_func: Async sleep (overridable for tests).
    """

    def __init__(
        self,
        rate: float,
        burst: int | None = None,
        *,
        time_func=time.monotonic,
        sleep_func=asyncio.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self._rate = float(rate)
        self._capacity = float(burst if burst is not None else max(1, round(rate)))
        self._time = time_func
        self._sleep = sleep_func
        self._buckets: dict[str, _Bucket] = {}
        self._registry_lock = asyncio.Lock()

    @staticmethod
    def host_of(url: str) -> str:
        """Extract a host key from a URL (falls back to the raw string)."""
        parsed = urlparse(url)
        return parsed.netloc or url

    async def _get_bucket(self, host: str) -> _Bucket:
        async with self._registry_lock:
            bucket = self._buckets.get(host)
            if bucket is None:
                bucket = _Bucket(
                    rate=self._rate,
                    capacity=self._capacity,
                    tokens=self._capacity,
                    updated=self._time(),
                )
                self._buckets[host] = bucket
            return bucket

    async def acquire(self, url: str) -> None:
        """Block until a token is available for ``url``'s host."""
        host = self.host_of(url)
        bucket = await self._get_bucket(host)
        async with bucket.lock:
            while True:
                now = self._time()
                elapsed = now - bucket.updated
                bucket.updated = now
                bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.rate)
                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    return
                # Wait just long enough for one token to accrue.
                deficit = 1.0 - bucket.tokens
                await self._sleep(deficit / bucket.rate)
