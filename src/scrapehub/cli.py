"""Typer CLI entrypoint for scrapehub.

Subcommands map to sanctioned sources. Each builds the resilient client/browser,
runs the scraper through the clean -> validate -> export pipeline, and prints a
run summary with metrics.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from scrapehub.config import get_settings
from scrapehub.core.browser import BrowserManager
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.rate_limiter import RateLimiter
from scrapehub.core.user_agents import UserAgentRotator
from scrapehub.logging_setup import (
    bind_run_context,
    clear_run_context,
    configure_logging,
    get_logger,
)
from scrapehub.pipeline.export import export_records
from scrapehub.scrapers.base import ScrapeResult
from scrapehub.scrapers.books_static import BooksStaticScraper
from scrapehub.scrapers.hackernews_api import HackerNewsApiScraper
from scrapehub.scrapers.quotes_js import QuotesJsScraper
from scrapehub.scrapers.quotes_scroll import QuotesScrollScraper
from scrapehub.scrapers.quotes_static import QuotesStaticScraper
from scrapehub.scrapers.wikipedia_api import WikipediaApiScraper

app = typer.Typer(
    add_completion=False,
    help="Async headless scraping for sanctioned sources (books/quotes/Wikipedia/HN).",
    no_args_is_help=True,
)


def _build_http_client(metrics: Metrics) -> AsyncHttpClient:
    """Assemble a resilient HTTP client from settings."""
    settings = get_settings()
    return AsyncHttpClient(
        proxy_pool=ProxyPool(proxies=settings.proxies),
        ua_rotator=UserAgentRotator(),
        rate_limiter=RateLimiter(rate=settings.rate_limit, burst=settings.rate_burst),
        timeout=settings.timeout,
        max_retries=settings.max_retries,
        metrics=metrics,
    )


def _build_browser(metrics: Metrics) -> BrowserManager:
    settings = get_settings()
    return BrowserManager(
        proxy_pool=ProxyPool(proxies=settings.proxies),
        ua_rotator=UserAgentRotator(),
        headless=True,
        timeout=settings.timeout,
    )


def _finalize(result: ScrapeResult, out: Path | None, model) -> None:
    """Export results and print a summary."""
    log = get_logger(source=result.source)
    settings = get_settings()
    if out is None:
        out = settings.ensure_output_dir() / result.source
    paths = export_records(result.records, out, model)
    log.info(
        "run.summary",
        records=len(result.records),
        csv=str(paths["csv"]),
        json=str(paths["json"]),
        metrics=result.metrics,
    )
    typer.echo(
        f"[{result.source}] wrote {len(result.records)} records -> "
        f"{paths['csv']} , {paths['json']}"
    )


def _bootstrap() -> Metrics:
    settings = get_settings()
    configure_logging(settings.log_format, settings.log_level)
    bind_run_context(source="cli")
    return Metrics()


@app.command()
def books(
    pages: int = typer.Option(1, "--pages", min=1, help="Catalogue pages to crawl."),
    out: Path | None = typer.Option(None, "--out", help="Output base path (no ext)."),
) -> None:
    """Scrape books.toscrape.com catalogue (static BeautifulSoup)."""
    metrics = _bootstrap()

    async def _run() -> None:
        async with _build_http_client(metrics) as client:
            scraper = BooksStaticScraper(client, metrics=metrics)
            result = await scraper.run(max_pages=pages)
            _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


@app.command(name="quotes-static")
def quotes_static(
    pages: int = typer.Option(1, "--pages", min=1),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Scrape static quotes.toscrape.com (BeautifulSoup + pagination)."""
    metrics = _bootstrap()

    async def _run() -> None:
        async with _build_http_client(metrics) as client:
            scraper = QuotesStaticScraper(client, metrics=metrics)
            result = await scraper.run(max_pages=pages)
            _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


@app.command(name="quotes-js")
def quotes_js(
    pages: int = typer.Option(1, "--pages", min=1),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Scrape quotes.toscrape.com/js (Playwright JS rendering)."""
    metrics = _bootstrap()

    async def _run() -> None:
        async with _build_browser(metrics) as browser:
            scraper = QuotesJsScraper(browser, metrics=metrics)
            result = await scraper.run(max_pages=pages)
            _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


@app.command(name="quotes-scroll")
def quotes_scroll(
    use_api: bool = typer.Option(
        True,
        "--api/--browser",
        help="Walk the AJAX JSON endpoint (default) or drive real scroll.",
    ),
    max_pages: int = typer.Option(50, "--max-pages", min=1),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Scrape quotes.toscrape.com/scroll (infinite scroll + AJAX)."""
    metrics = _bootstrap()

    async def _run() -> None:
        if use_api:
            async with _build_http_client(metrics) as client:
                scraper = QuotesScrollScraper(client=client, metrics=metrics)
                result = await scraper.run_via_api(max_pages=max_pages)
                _finalize(result, out, scraper.model)
        else:
            async with _build_browser(metrics) as browser:
                scraper = QuotesScrollScraper(browser=browser, metrics=metrics)
                result = await scraper.run(max_scrolls=max_pages)
                _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


@app.command()
def wikipedia(
    titles: list[str] = typer.Argument(..., help="Page titles to fetch summaries for."),
    lang: str = typer.Option("en", "--lang"),
    concurrency: int | None = typer.Option(None, "--concurrency", min=1),
    batch: int | None = typer.Option(None, "--batch", min=1),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Fetch Wikipedia REST API page summaries (rotating proxies + batching)."""
    metrics = _bootstrap()
    settings = get_settings()

    async def _run() -> None:
        async with _build_http_client(metrics) as client:
            scraper = WikipediaApiScraper(
                client,
                lang=lang,
                concurrency=concurrency or settings.concurrency,
                batch_size=batch or settings.batch_size,
                metrics=metrics,
            )
            result = await scraper.run(titles=titles)
            _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


@app.command()
def hackernews(
    limit: int = typer.Option(30, "--limit", min=1, help="Top stories to fetch."),
    concurrency: int | None = typer.Option(None, "--concurrency", min=1),
    batch: int | None = typer.Option(None, "--batch", min=1),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Fetch Hacker News top stories (Firebase API + batched item fetches)."""
    metrics = _bootstrap()
    settings = get_settings()

    async def _run() -> None:
        async with _build_http_client(metrics) as client:
            scraper = HackerNewsApiScraper(
                client,
                concurrency=concurrency or settings.concurrency,
                batch_size=batch or settings.batch_size,
                metrics=metrics,
            )
            result = await scraper.run(limit=limit)
            _finalize(result, out, scraper.model)

    try:
        asyncio.run(_run())
    finally:
        clear_run_context()


if __name__ == "__main__":  # pragma: no cover
    app()
