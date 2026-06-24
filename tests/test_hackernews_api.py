"""Tests for the Hacker News Firebase API scraper (mocked httpx)."""

from __future__ import annotations

import copy

import httpx
import pytest

from scrapehub.models.story import Story
from scrapehub.scrapers.hackernews_api import HackerNewsApiScraper, parse_item


def test_parse_item_maps_fields(hackernews_payload: dict):
    record = parse_item(hackernews_payload)
    assert record["id"] == 8863
    assert record["by"] == "pg"
    assert record["score"] == 311


@pytest.mark.asyncio
async def test_scraper_fetches_top_stories(make_client, hackernews_payload: dict):
    ids = [101, 102, 103]

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "topstories" in url:
            return httpx.Response(200, json=ids)
        # Return the item with an id derived from the URL.
        item = copy.deepcopy(hackernews_payload)
        item_id = int(url.split("/item/")[1].split(".json")[0])
        item["id"] = item_id
        return httpx.Response(200, json=item)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = HackerNewsApiScraper(client, concurrency=4, batch_size=2)
        result = await scraper.run(limit=3)

    assert len(result.records) == 3
    assert all(isinstance(s, Story) for s in result.records)
    assert {s.id for s in result.records} == {101, 102, 103}


@pytest.mark.asyncio
async def test_limit_truncates_id_list(make_client, hackernews_payload: dict):
    ids = list(range(1, 101))
    fetched: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "topstories" in url:
            return httpx.Response(200, json=ids)
        item_id = int(url.split("/item/")[1].split(".json")[0])
        fetched.append(item_id)
        item = copy.deepcopy(hackernews_payload)
        item["id"] = item_id
        return httpx.Response(200, json=item)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = HackerNewsApiScraper(client, concurrency=5, batch_size=5)
        await scraper.run(limit=10)

    assert len(fetched) == 10
