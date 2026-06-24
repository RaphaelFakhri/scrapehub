"""Tests for the async token-bucket rate limiter."""

from __future__ import annotations

import pytest

from scrapehub.core.rate_limiter import RateLimiter


def make_fake_clock():
    state = {"t": 0.0}

    def now() -> float:
        return state["t"]

    async def sleep(seconds: float) -> None:
        state["t"] += seconds

    return state, now, sleep


@pytest.mark.asyncio
async def test_burst_allows_immediate_requests():
    _state, now, sleep = make_fake_clock()
    limiter = RateLimiter(rate=1.0, burst=3, time_func=now, sleep_func=sleep)
    # First 3 acquisitions should not advance the clock (burst capacity).
    for _ in range(3):
        await limiter.acquire("https://example.com/x")
    assert _state["t"] == 0.0


@pytest.mark.asyncio
async def test_throttles_after_burst_exhausted():
    state, now, sleep = make_fake_clock()
    limiter = RateLimiter(rate=2.0, burst=1, time_func=now, sleep_func=sleep)
    await limiter.acquire("https://example.com/")  # consumes the single token
    await limiter.acquire("https://example.com/")  # must wait ~1/rate seconds
    assert state["t"] == pytest.approx(0.5, rel=1e-6)


@pytest.mark.asyncio
async def test_per_host_buckets_are_independent():
    state, now, sleep = make_fake_clock()
    limiter = RateLimiter(rate=1.0, burst=1, time_func=now, sleep_func=sleep)
    await limiter.acquire("https://a.com/")
    await limiter.acquire("https://b.com/")  # different host, own bucket
    assert state["t"] == 0.0


def test_host_of_extracts_netloc():
    assert RateLimiter.host_of("https://example.com/path?x=1") == "example.com"


def test_invalid_rate_raises():
    with pytest.raises(ValueError):
        RateLimiter(rate=0)
