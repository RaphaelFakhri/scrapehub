"""Tests for user-agent rotation and header generation."""

from __future__ import annotations

import pytest

from scrapehub.core.user_agents import USER_AGENTS, UserAgentRotator


def test_round_robin_cycles_through_pool():
    rotator = UserAgentRotator(strategy="round_robin")
    first_cycle = [rotator.next_agent() for _ in USER_AGENTS]
    assert set(first_cycle) == set(USER_AGENTS)
    # Wraps around.
    assert rotator.next_agent() == first_cycle[0]


def test_random_strategy_with_seed_is_reproducible():
    a = UserAgentRotator(strategy="random", seed=1)
    b = UserAgentRotator(strategy="random", seed=1)
    assert [a.next_agent() for _ in range(5)] == [b.next_agent() for _ in range(5)]


def test_headers_contain_user_agent_and_accept():
    rotator = UserAgentRotator()
    headers = rotator.headers()
    assert "User-Agent" in headers
    assert headers["Accept"].startswith("text/html")
    assert headers["Accept-Language"].startswith("en-US")


def test_chromium_headers_include_sec_fetch():
    rotator = UserAgentRotator()
    chrome_ua = USER_AGENTS[0]
    headers = rotator.headers(chrome_ua)
    assert headers["Sec-Fetch-Mode"] == "navigate"


def test_firefox_headers_omit_sec_fetch():
    rotator = UserAgentRotator()
    firefox_ua = next(ua for ua in USER_AGENTS if "Firefox" in ua)
    headers = rotator.headers(firefox_ua)
    assert "Sec-Fetch-Mode" not in headers


def test_empty_pool_raises():
    with pytest.raises(ValueError):
        UserAgentRotator(user_agents=())
