"""Static BeautifulSoup scraper + shared parser for quotes.toscrape.com.

The static, ``/js`` and ``/scroll`` variants all render the same DOM shape, so
the parsing logic lives here and is reused by the Playwright-based scrapers.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.models.quote import Quote
from scrapehub.scrapers.base import BaseScraper
from scrapehub.selectors.registry import SELECTORS, select_one, select_text

BASE_URL = "https://quotes.toscrape.com/"


def parse_quotes_html(html: str) -> list[dict]:
    """Parse rendered quotes HTML into raw quote dicts (pure, offline-testable)."""
    soup = BeautifulSoup(html, "lxml")
    sel = SELECTORS["quotes"]
    records: list[dict] = []
    for node in soup.select(sel["quote"].primary) or soup.select(sel["quote"].fallbacks[0]):
        text = select_text(node, sel["text"])
        author = select_text(node, sel["author"])
        tags = [a.get_text(strip=True) for a in node.select(sel["tags"].primary)]
        if not tags:
            for fallback in sel["tags"].fallbacks:
                tags = [a.get_text(strip=True) for a in node.select(fallback)]
                if tags:
                    break
        records.append({"text": text, "author": author, "tags": tags})
    return records


def find_next_page(html: str, *, page_url: str) -> str | None:
    """Return absolute URL of the next quotes page, or ``None``."""
    soup = BeautifulSoup(html, "lxml")
    next_el = select_one(soup, SELECTORS["quotes"]["next_page"])
    if next_el is None:
        return None
    href = next_el.get("href")
    return urljoin(page_url, href) if href else None


class QuotesStaticScraper(BaseScraper[Quote]):
    """Scrape static quotes.toscrape.com pages, following pagination."""

    source = "quotes-static"
    model = Quote

    def __init__(self, client: AsyncHttpClient, *, metrics: Metrics | None = None) -> None:
        super().__init__(metrics=metrics or client.metrics)
        self._client = client

    async def fetch(self, *, start_url: str = BASE_URL, max_pages: int = 1) -> list[str]:
        pages: list[str] = []
        url: str | None = start_url
        count = 0
        while url and count < max_pages:
            html = await self._client.get_text(url)
            pages.append(html)
            url = find_next_page(html, page_url=url)
            count += 1
        return pages

    def parse(self, raw: list[str]) -> list[dict]:
        records: list[dict] = []
        for html in raw:
            records.extend(parse_quotes_html(html))
        return records
