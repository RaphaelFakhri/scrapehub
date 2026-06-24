"""Example: scrape the books.toscrape.com catalogue and export CSV+JSON.

Run with:  python examples/run_books.py
"""

from __future__ import annotations

import asyncio

from scrapehub.config import get_settings
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.rate_limiter import RateLimiter
from scrapehub.logging_setup import configure_logging
from scrapehub.pipeline.export import export_records
from scrapehub.scrapers.books_static import BooksStaticScraper


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_format, settings.log_level)
    async with AsyncHttpClient(
        proxy_pool=ProxyPool(proxies=settings.proxies),
        rate_limiter=RateLimiter(rate=settings.rate_limit, burst=settings.rate_burst),
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    ) as client:
        scraper = BooksStaticScraper(client)
        result = await scraper.run(max_pages=2)
        out = settings.ensure_output_dir() / "books"
        paths = export_records(result.records, out, scraper.model)
        print(f"Wrote {len(result.records)} books -> {paths['csv']}, {paths['json']}")


if __name__ == "__main__":
    asyncio.run(main())
