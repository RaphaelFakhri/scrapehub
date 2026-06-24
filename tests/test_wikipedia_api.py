"""Tests for the Wikipedia REST API scraper (mocked httpx)."""

from __future__ import annotations

import httpx
import pytest

from scrapehub.models.article import Article
from scrapehub.scrapers.wikipedia_api import WikipediaApiScraper, parse_summary


def test_parse_summary_maps_fields(wikipedia_payload: dict):
    record = parse_summary(wikipedia_payload, lang="en")
    assert record["title"] == "Web scraping"
    assert record["url"] == "https://en.wikipedia.org/wiki/Web_scraping"
    assert record["description"].startswith("Data scraping")


@pytest.mark.asyncio
async def test_scraper_fetches_multiple_titles(make_client, wikipedia_payload: dict):
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=wikipedia_payload)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = WikipediaApiScraper(client, concurrency=4, batch_size=2)
        result = await scraper.run(titles=["Web scraping", "Asyncio", "Python"])

    assert len(result.records) == 3
    assert all(isinstance(a, Article) for a in result.records)
    # Title with space is URL-encoded with underscore.
    assert any("Web_scraping" in u for u in requested)


@pytest.mark.asyncio
async def test_failed_title_is_skipped_not_fatal(make_client, wikipedia_payload: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        if "Missing" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, json=wikipedia_payload)

    transport = httpx.MockTransport(handler)
    async with make_client(transport, max_retries=1) as client:
        scraper = WikipediaApiScraper(client, concurrency=2, batch_size=2)
        result = await scraper.run(titles=["Web scraping", "Missing Page"])

    assert len(result.records) == 1
