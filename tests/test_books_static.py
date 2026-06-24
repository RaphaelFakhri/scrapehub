"""Tests for the static books scraper (parser + paginated fetch, mocked)."""

from __future__ import annotations

import httpx
import pytest

from scrapehub.models.book import Book
from scrapehub.scrapers.books_static import (
    BooksStaticScraper,
    find_next_page,
    parse_books_html,
)


def test_parse_books_html_extracts_fields(books_html: str):
    records = parse_books_html(books_html)
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "A Light in the Attic"
    assert first["price"] == pytest.approx(51.77)
    assert first["currency"] == "£"
    assert first["rating"] == "Three"
    assert first["in_stock"] is True
    assert first["url"].endswith("a-light-in-the-attic_1000/index.html")


def test_parsed_records_validate_into_book_model(books_html: str):
    records = parse_books_html(books_html)
    books = [Book.model_validate(r) for r in records]
    assert books[0].rating == 3  # word -> int coercion
    assert books[1].rating == 1


def test_find_next_page(books_html: str):
    nxt = find_next_page(books_html, page_url="https://books.toscrape.com/catalogue/page-1.html")
    assert nxt == "https://books.toscrape.com/catalogue/page-2.html"


@pytest.mark.asyncio
async def test_scraper_run_offline(make_client, books_html: str):
    def handler(request: httpx.Request) -> httpx.Response:
        # Serve the same page but strip the next-link on page 2 to stop crawl.
        if "page-2" in str(request.url):
            html = books_html.replace('<li class="next"><a href="page-2.html">next</a></li>', "")
            return httpx.Response(200, text=html)
        return httpx.Response(200, text=books_html)

    transport = httpx.MockTransport(handler)
    async with make_client(transport) as client:
        scraper = BooksStaticScraper(client)
        result = await scraper.run(
            start_url="https://books.toscrape.com/catalogue/page-1.html", max_pages=2
        )
    assert len(result.records) == 4  # 2 books x 2 pages
    assert result.report.summary()["quarantined"] == 0
