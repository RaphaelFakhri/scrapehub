"""Tests for the infinite-scroll scraper via its mocked AJAX JSON endpoint."""

from __future__ import annotations

import copy

import httpx
import pytest

from scrapehub.scrapers.quotes_scroll import QuotesScrollScraper, parse_api_payload


def test_parse_api_payload_maps_author_and_tags(scroll_api_payload: dict):
    records = parse_api_payload(scroll_api_payload)
    assert len(records) == 2
    assert records[0]["author"] == "Albert Einstein"
    assert records[0]["tags"] == ["change", "deep-thoughts", "thinking", "world"]


@pytest.mark.asyncio
async def test_scroll_paginates_until_has_next_false(make_client, scroll_api_payload: dict):
    page_one = copy.deepcopy(scroll_api_payload)
    page_one["has_next"] = True
    page_two = copy.deepcopy(scroll_api_payload)
    page_two["page"] = 2
    page_two["has_next"] = False

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        return httpx.Response(200, json=page_one if page == "1" else page_two)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = QuotesScrollScraper(client=client)
        result = await scraper.run_via_api(max_pages=10)

    # 2 quotes per page x 2 pages.
    assert len(result.records) == 4
    assert result.report.summary()["quarantined"] == 0


@pytest.mark.asyncio
async def test_scroll_respects_max_pages(make_client, scroll_api_payload: dict):
    always_more = copy.deepcopy(scroll_api_payload)
    always_more["has_next"] = True

    seen_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_pages.append(request.url.params.get("page"))
        return httpx.Response(200, json=always_more)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = QuotesScrollScraper(client=client)
        await scraper.run_via_api(max_pages=3)

    assert seen_pages == ["1", "2", "3"]
