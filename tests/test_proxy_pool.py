"""Tests for the rotating proxy pool."""

from __future__ import annotations

from scrapehub.core.proxy_pool import ProxyPool


def test_empty_pool_returns_none():
    pool = ProxyPool(proxies=[])
    assert pool.empty is True
    assert pool.get() is None


def test_round_robin_rotation():
    pool = ProxyPool(proxies=["http://a", "http://b", "http://c"], strategy="round_robin")
    picks = [pool.get() for _ in range(6)]
    assert picks == [
        "http://a",
        "http://b",
        "http://c",
        "http://a",
        "http://b",
        "http://c",
    ]


def test_random_strategy_is_deterministic_with_seed():
    pool = ProxyPool(proxies=["http://a", "http://b"], strategy="random", seed=42)
    picks = {pool.get() for _ in range(10)}
    assert picks <= {"http://a", "http://b"}


def test_failure_triggers_cooldown_and_skips_proxy():
    pool = ProxyPool(
        proxies=["http://a", "http://b"],
        strategy="round_robin",
        max_failures=2,
        cooldown_seconds=999,
    )
    # Trip 'a' offline.
    pool.report_failure("http://a")
    pool.report_failure("http://a")
    available = pool.available()
    assert "http://a" not in available
    assert "http://b" in available
    # get() should only return the healthy proxy now.
    assert {pool.get() for _ in range(4)} == {"http://b"}


def test_success_resets_failures():
    pool = ProxyPool(proxies=["http://a"], max_failures=2, cooldown_seconds=999)
    pool.report_failure("http://a")
    pool.report_success("http://a")
    pool.report_failure("http://a")  # only one failure since reset
    assert "http://a" in pool.available()


def test_stats_snapshot():
    pool = ProxyPool(proxies=["http://a"])
    pool.report_success("http://a")
    stats = pool.stats()
    assert stats["http://a"]["successes"] == 1
