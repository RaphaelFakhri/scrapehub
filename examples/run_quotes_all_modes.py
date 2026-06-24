"""Example: scrape quotes.toscrape.com in all three modes.

* static  -> plain HTTP + BeautifulSoup
* /js     -> Playwright JS rendering
* /scroll -> AJAX JSON endpoint (infinite scroll)

Run with:  python examples/run_quotes_all_modes.py
Note: the /js path needs `python -m playwright install chromium`.
"""

from __future__ import annotations

import asyncio

from scrapehub.config import get_settings
from scrapehub.core.browser import BrowserManager
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.rate_limiter import RateLimiter
from scrapehub.logging_setup import configure_logging
from scrapehub.pipeline.export import export_records
from scrapehub.scrapers.quotes_js import QuotesJsScraper
from scrapehub.scrapers.quotes_scroll import QuotesScrollScraper
from scrapehub.scrapers.quotes_static import QuotesStaticScraper


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_format, settings.log_level)
    out_dir = settings.ensure_output_dir()

    async with AsyncHttpClient(
        rate_limiter=RateLimiter(rate=settings.rate_limit, burst=settings.rate_burst),
        timeout=settings.timeout,
    ) as client:
        static = QuotesStaticScraper(client)
        static_result = await static.run(max_pages=2)
        export_records(static_result.records, out_dir / "quotes_static", static.model)

        scroll = QuotesScrollScraper(client=client)
        scroll_result = await scroll.run_via_api(max_pages=10)
        export_records(scroll_result.records, out_dir / "quotes_scroll", scroll.model)

    async with BrowserManager(headless=True, timeout=settings.timeout) as browser:
        js = QuotesJsScraper(browser)
        js_result = await js.run(max_pages=2)
        export_records(js_result.records, out_dir / "quotes_js", js.model)

    print(
        f"static={len(static_result.records)} "
        f"scroll={len(scroll_result.records)} "
        f"js={len(js_result.records)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
