"""Hacker News Firebase API client.

Fetches the top-story id list, then fetches each item concurrently in bounded
batches via the resilient HTTP client.
"""

from __future__ import annotations

from typing import Any

from scrapehub.core.batching import process_in_batches
from scrapehub.core.http_client import AsyncHttpClient
from scrapehub.core.metrics import Metrics
from scrapehub.models.story import Story
from scrapehub.scrapers.base import BaseScraper

TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


def parse_item(payload: dict[str, Any]) -> dict:
    """Map a Firebase item payload into a raw Story dict."""
    return {
        "id": payload.get("id"),
        "title": payload.get("title", ""),
        "by": payload.get("by", ""),
        "score": payload.get("score", 0),
        "descendants": payload.get("descendants", 0),
        "time": payload.get("time", 0),
        "url": payload.get("url"),
    }


class HackerNewsApiScraper(BaseScraper[Story]):
    """Fetch the top Hacker News stories."""

    source = "hackernews"
    model = Story

    def __init__(
        self,
        client: AsyncHttpClient,
        *,
        concurrency: int = 8,
        batch_size: int = 20,
        metrics: Metrics | None = None,
    ) -> None:
        super().__init__(metrics=metrics or client.metrics)
        self._client = client
        self._concurrency = concurrency
        self._batch_size = batch_size

    def _item_url(self, item_id: int) -> str:
        return ITEM_URL.format(item_id=item_id)

    async def _fetch_item(self, item_id: int) -> dict | None:
        try:
            payload = await self._client.get_json(self._item_url(item_id))
        except Exception as exc:  # noqa: BLE001 - logged + quarantined
            self.log.warning("hn.item.failed", item_id=item_id, error=repr(exc))
            self.metrics.record_failure(self.source)
            return None
        if not payload or payload.get("type") not in {None, "story"}:
            return None
        return parse_item(payload)

    async def fetch(self, *, limit: int = 30) -> list[dict]:
        """Fetch the first ``limit`` top stories with bounded concurrency."""
        ids: list[int] = await self._client.get_json(TOPSTORIES_URL)
        selected = ids[:limit]
        self.log.info("hn.topstories", total=len(ids), selected=len(selected))
        results = await process_in_batches(
            selected,
            self._fetch_item,
            batch_size=self._batch_size,
            concurrency=self._concurrency,
        )
        return [r for r in results if r is not None]

    def parse(self, raw: list[dict]) -> list[dict]:
        return raw
