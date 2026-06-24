"""Playwright scraper for quotes.toscrape.com/scroll (infinite scroll + AJAX).

The ``/scroll`` page lazy-loads quotes via an AJAX endpoint
(``/api/quotes?page=N``) as you scroll. Two strategies are supported:

* :meth:`fetch` drives a real headless browser through the scroll loop.
* :meth:`fetch_via_api` walks the JSON AJAX endpoint directly — this is what the
  offline test mocks, so the pagination logic is verified without Chromium.
"""

from __future__ import annotations

from typing import Any

from scrapehub.core.browser import BrowserManager
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.models.quote import Quote
from scrapehub.scrapers.base import BaseScraper
from scrapehub.scrapers.quotes_static import parse_quotes_html
from scrapehub.selectors.registry import SELECTORS

SCROLL_URL = "https://quotes.toscrape.com/scroll"
API_URL = "https://quotes.toscrape.com/api/quotes"


def parse_api_payload(payload: dict[str, Any]) -> list[dict]:
    """Map one AJAX JSON page into raw quote dicts."""
    records: list[dict] = []
    for q in payload.get("quotes", []):
        author = q.get("author")
        author_name = author.get("name") if isinstance(author, dict) else author
        records.append(
            {
                "text": q.get("text", ""),
                "author": author_name or "",
                "tags": list(q.get("tags", [])),
            }
        )
    return records


class QuotesScrollScraper(BaseScraper[Quote]):
    """Infinite-scroll scraper with a browser path and an AJAX path."""

    source = "quotes-scroll"
    model = Quote

    def __init__(
        self,
        *,
        browser: BrowserManager | None = None,
        client: AsyncHttpClient | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        super().__init__(metrics=metrics)
        self._browser = browser
        self._client = client

    async def fetch(self, *, url: str = SCROLL_URL, max_scrolls: int = 20) -> list[str]:
        """Drive the real infinite-scroll page and return final HTML (one item)."""
        if self._browser is None:
            raise RuntimeError("browser path requires a BrowserManager")
        item_selector = SELECTORS["quotes"]["quote"].primary
        html = await self._browser.scroll_collect(
            url, item_selector=item_selector, max_scrolls=max_scrolls
        )
        return [html]

    async def fetch_via_api(self, *, api_url: str = API_URL, max_pages: int = 50) -> list[dict]:
        """Walk the AJAX JSON endpoint page-by-page until ``has_next`` is false.

        Returns a flat list of raw quote dicts. This is the offline-tested path.
        """
        if self._client is None:
            raise RuntimeError("API path requires an AsyncHttpClient")
        records: list[dict] = []
        page = 1
        while page <= max_pages:
            payload = await self._client.get_json(api_url, params={"page": page})
            page_records = parse_api_payload(payload)
            records.extend(page_records)
            self.log.info("quotes_scroll.api.page", page=page, quotes=len(page_records))
            if not payload.get("has_next"):
                break
            page += 1
        return records

    def parse(self, raw: list[Any]) -> list[dict]:
        """Parse browser HTML pages or pass through API dicts."""
        records: list[dict] = []
        for item in raw:
            if isinstance(item, str):
                records.extend(parse_quotes_html(item))
            elif isinstance(item, dict):
                records.append(item)
        return records

    async def run_via_api(self, *, api_url: str = API_URL, max_pages: int = 50) -> Any:
        """Convenience: fetch via AJAX, then parse/validate through the pipeline."""
        self.log.info("scrape.start", mode="api", api_url=api_url)
        raw = await self.fetch_via_api(api_url=api_url, max_pages=max_pages)
        report = self.validate(self.parse(raw))
        self.log.info("scrape.done", **report.summary())
        from scrapehub.scrapers.base import ScrapeResult

        return ScrapeResult(
            source=self.source,
            records=list(report.valid),
            report=report,
            metrics=self.metrics.summary(),
        )
