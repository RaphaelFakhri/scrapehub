"""Shared pytest fixtures. The whole suite runs OFFLINE.

Network is mocked with ``respx`` (httpx) and Playwright is never launched — the
JS/scroll scrapers are tested through their pure parsers / AJAX paths instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.rate_limiter import RateLimiter

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Return the raw text of a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json_fixture(name: str) -> dict:
    """Return a parsed JSON fixture."""
    return json.loads(load_fixture(name))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def books_html() -> str:
    return load_fixture("books_page.html")


@pytest.fixture
def quotes_html() -> str:
    return load_fixture("quotes_page.html")


@pytest.fixture
def scroll_api_payload() -> dict:
    return load_json_fixture("quotes_scroll_api.json")


@pytest.fixture
def wikipedia_payload() -> dict:
    return load_json_fixture("wikipedia_summary.json")


@pytest.fixture
def hackernews_payload() -> dict:
    return load_json_fixture("hackernews_item.json")


@pytest.fixture
def fast_rate_limiter() -> RateLimiter:
    """A rate limiter with a no-op clock so tests never actually sleep."""

    async def _no_sleep(_seconds: float) -> None:
        return None

    return RateLimiter(rate=1000.0, burst=1000, sleep_func=_no_sleep)


@pytest.fixture
def make_client(fast_rate_limiter: RateLimiter):
    """Factory building an AsyncHttpClient bound to a respx MockTransport."""

    def _factory(transport: httpx.MockTransport, **kwargs) -> AsyncHttpClient:
        return AsyncHttpClient(
            proxy_pool=ProxyPool(proxies=[]),
            rate_limiter=fast_rate_limiter,
            transport=transport,
            max_retries=kwargs.pop("max_retries", 3),
            **kwargs,
        )

    return _factory
