"""Example: fetch from the Wikipedia REST API and Hacker News Firebase API.

Run with:  python examples/run_apis.py
"""

from __future__ import annotations

import asyncio

from scrapehub.config import get_settings
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.rate_limiter import RateLimiter
from scrapehub.logging_setup import configure_logging
from scrapehub.pipeline.export import export_records
from scrapehub.scrapers.hackernews_api import HackerNewsApiScraper
from scrapehub.scrapers.wikipedia_api import WikipediaApiScraper


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_format, settings.log_level)
    out_dir = settings.ensure_output_dir()

    async with AsyncHttpClient(
        proxy_pool=ProxyPool(proxies=settings.proxies),
        rate_limiter=RateLimiter(rate=settings.rate_limit, burst=settings.rate_burst),
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    ) as client:
        wiki = WikipediaApiScraper(
            client, concurrency=settings.concurrency, batch_size=settings.batch_size
        )
        wiki_result = await wiki.run(
            titles=["Web scraping", "Python (programming language)", "Asyncio"]
        )
        export_records(wiki_result.records, out_dir / "wikipedia", wiki.model)

        hn = HackerNewsApiScraper(
            client, concurrency=settings.concurrency, batch_size=settings.batch_size
        )
        hn_result = await hn.run(limit=10)
        export_records(hn_result.records, out_dir / "hackernews", hn.model)

    print(f"wikipedia={len(wiki_result.records)} hackernews={len(hn_result.records)}")


if __name__ == "__main__":
    asyncio.run(main())
