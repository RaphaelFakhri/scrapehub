"""Playwright scraper for quotes.toscrape.com/js (JS-rendered content).

The ``/js`` page builds the DOM client-side from an inline JS array, so a plain
HTTP fetch returns an empty shell. We render with Chromium, wait for the quote
nodes to appear, then reuse the shared HTML parser.
"""

from __future__ import annotations

from scrapehub.core.browser import BrowserManager
from scrapehub.core.metrics import Metrics
from scrapehub.models.quote import Quote
from scrapehub.scrapers.base import BaseScraper
from scrapehub.scrapers.quotes_static import parse_quotes_html
from scrapehub.selectors.registry import SELECTORS

JS_URL = "https://quotes.toscrape.com/js/"


class QuotesJsScraper(BaseScraper[Quote]):
    """Render the JS quotes page with Playwright and extract quotes.

    Pagination on ``/js`` uses ``/js/page/N/`` URLs; we render each page until no
    quotes remain or ``max_pages`` is reached.
    """

    source = "quotes-js"
    model = Quote

    def __init__(self, browser: BrowserManager, *, metrics: Metrics | None = None) -> None:
        super().__init__(metrics=metrics)
        self._browser = browser

    async def fetch(self, *, base_url: str = JS_URL, max_pages: int = 1) -> list[str]:
        """Render each page and return its post-JS HTML."""
        quote_selector = SELECTORS["quotes"]["quote"].primary
        pages: list[str] = []
        for page_num in range(1, max_pages + 1):
            url = base_url if page_num == 1 else f"{base_url.rstrip('/')}/page/{page_num}/"
            html = await self._browser.render(url, wait_for_selector=quote_selector)
            parsed = parse_quotes_html(html)
            if not parsed:
                break
            pages.append(html)
            self.log.info("quotes_js.page.rendered", url=url, quotes=len(parsed))
        return pages

    def parse(self, raw: list[str]) -> list[dict]:
        records: list[dict] = []
        for html in raw:
            records.extend(parse_quotes_html(html))
        return records
