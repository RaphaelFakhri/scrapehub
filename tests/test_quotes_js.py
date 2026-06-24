"""Tests for the JS quotes scraper, mocking the Playwright browser.

We never launch Chromium. Instead we substitute a fake BrowserManager whose
``render`` returns canned post-JS HTML, then assert the shared parser + pipeline
produce valid quotes.
"""

from __future__ import annotations

import pytest

from scrapehub.models.quote import Quote
from scrapehub.scrapers.quotes_js import QuotesJsScraper


class FakeBrowser:
    """Stand-in for BrowserManager that returns fixture HTML once."""

    def __init__(self, html: str) -> None:
        self._html = html
        self.calls: list[str] = []

    async def render(self, url: str, *, wait_for_selector=None, wait_until="networkidle") -> str:
        self.calls.append(url)
        # Page 1 returns quotes; subsequent pages return an empty shell to stop.
        if "page/2" in url:
            return "<html><body></body></html>"
        return self._html


@pytest.mark.asyncio
async def test_quotes_js_renders_and_parses(quotes_html: str):
    browser = FakeBrowser(quotes_html)
    scraper = QuotesJsScraper(browser)  # type: ignore[arg-type]
    result = await scraper.run(max_pages=3)
    assert len(result.records) == 2
    assert all(isinstance(q, Quote) for q in result.records)
    assert result.records[0].author == "Albert Einstein"


@pytest.mark.asyncio
async def test_quotes_js_stops_on_empty_page(quotes_html: str):
    browser = FakeBrowser(quotes_html)
    scraper = QuotesJsScraper(browser)  # type: ignore[arg-type]
    await scraper.run(max_pages=5)
    # Stops after page 2 returns no quotes.
    assert any("page/2" in c for c in browser.calls)
    assert len(browser.calls) == 2
