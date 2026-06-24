"""Wikipedia REST API client returning page summaries.

Uses the resilient :class:`AsyncHttpClient` (rotating proxies, UA rotation, rate
limiting, retry) and batched concurrency to fetch many summaries at once.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from scrapehub.core.batching import process_in_batches
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.models.article import Article
from scrapehub.scrapers.base import BaseScraper

SUMMARY_ENDPOINT = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"


def parse_summary(payload: dict[str, Any], *, lang: str = "en") -> dict:
    """Map a REST summary payload into a raw Article dict."""
    content_urls = payload.get("content_urls", {}) or {}
    desktop = content_urls.get("desktop", {}) or {}
    url = desktop.get("page") or payload.get("title", "")
    return {
        "title": payload.get("title", ""),
        "extract": payload.get("extract", ""),
        "description": payload.get("description"),
        "url": url,
        "lang": lang,
    }


class WikipediaApiScraper(BaseScraper[Article]):
    """Fetch Wikipedia page summaries for a list of titles."""

    source = "wikipedia"
    model = Article

    def __init__(
        self,
        client: AsyncHttpClient,
        *,
        lang: str = "en",
        concurrency: int = 8,
        batch_size: int = 20,
        metrics: Metrics | None = None,
    ) -> None:
        super().__init__(metrics=metrics or client.metrics)
        self._client = client
        self._lang = lang
        self._concurrency = concurrency
        self._batch_size = batch_size

    def _url_for(self, title: str) -> str:
        return SUMMARY_ENDPOINT.format(lang=self._lang, title=quote(title.replace(" ", "_")))

    async def _fetch_one(self, title: str) -> dict | None:
        try:
            payload = await self._client.get_json(self._url_for(title))
        except Exception as exc:  # noqa: BLE001 - logged + quarantined
            self.log.warning("wikipedia.fetch.failed", title=title, error=repr(exc))
            self.metrics.record_failure(self.source)
            return None
        return parse_summary(payload, lang=self._lang)

    async def fetch(self, *, titles: list[str]) -> list[dict]:
        """Fetch summaries for ``titles`` with bounded concurrent batches."""
        results = await process_in_batches(
            titles,
            self._fetch_one,
            batch_size=self._batch_size,
            concurrency=self._concurrency,
        )
        return [r for r in results if r is not None]

    def parse(self, raw: list[dict]) -> list[dict]:
        return raw
