"""Static BeautifulSoup scraper for books.toscrape.com with pagination."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.models.book import Book
from scrapehub.pipeline.clean import normalize_whitespace, parse_currency
from scrapehub.scrapers.base import BaseScraper
from scrapehub.selectors.registry import SELECTORS, select_one, select_text

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

_RATING_CLASSES = {"One", "Two", "Three", "Four", "Five", "Zero"}


def parse_books_html(html: str, *, page_url: str = BASE_URL) -> list[dict]:
    """Parse a books listing page into raw book dicts.

    Pure function (no network) so it is exercised directly by offline tests.
    """
    soup = BeautifulSoup(html, "lxml")
    sel = SELECTORS["books"]
    records: list[dict] = []
    for pod in soup.select(sel["product"].primary) or soup.select(sel["product"].fallbacks[0]):
        title_el = select_one(pod, sel["title"])
        title = title_el.get("title") or title_el.get_text(strip=True) if title_el else ""
        href = title_el.get("href") if title_el else None
        url = urljoin(page_url, href) if href else page_url

        price_text = select_text(pod, sel["price"])
        try:
            amount, currency = parse_currency(price_text)
        except ValueError:
            amount, currency = 0.0, "GBP"

        rating_el = select_one(pod, sel["rating"])
        rating_word = "Zero"
        if rating_el is not None:
            classes = rating_el.get("class") or []
            rating_word = next((c for c in classes if c in _RATING_CLASSES), "Zero")

        availability = normalize_whitespace(select_text(pod, sel["availability"]))

        records.append(
            {
                "title": title,
                "price": amount,
                "currency": currency,
                "rating": rating_word,
                "availability": availability,
                "in_stock": "in stock" in availability.lower(),
                "url": url,
            }
        )
    return records


def find_next_page(html: str, *, page_url: str) -> str | None:
    """Return the absolute URL of the next page, or ``None`` if last page."""
    soup = BeautifulSoup(html, "lxml")
    next_el = select_one(soup, SELECTORS["books"]["next_page"])
    if next_el is None:
        return None
    href = next_el.get("href")
    return urljoin(page_url, href) if href else None


class BooksStaticScraper(BaseScraper[Book]):
    """Scrape the books.toscrape.com catalogue, following pagination."""

    source = "books"
    model = Book

    def __init__(self, client: AsyncHttpClient, *, metrics: Metrics | None = None) -> None:
        super().__init__(metrics=metrics or client.metrics)
        self._client = client

    async def fetch(self, *, start_url: str = CATALOGUE_URL, max_pages: int = 1) -> list[str]:
        """Fetch up to ``max_pages`` listing pages, following the next link."""
        pages: list[str] = []
        url: str | None = start_url
        count = 0
        while url and count < max_pages:
            html = await self._client.get_text(url)
            pages.append(html)
            self.log.info("books.page.fetched", url=url, index=count)
            url = find_next_page(html, page_url=url)
            count += 1
        return pages

    def parse(self, raw: list[str]) -> list[dict]:
        records: list[dict] = []
        for html in raw:
            records.extend(parse_books_html(html, page_url=BASE_URL))
        return records
