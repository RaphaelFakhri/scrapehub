"""Async batching utilities for scale.

Combines bounded concurrency (an ``asyncio.Semaphore``) with chunking so large
id/url lists can be processed at scale without exhausting connections or the
event loop. Results preserve input order.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def chunked(items: Sequence[T], size: int) -> list[list[T]]:
    """Split ``items`` into chunks of at most ``size``."""
    if size < 1:
        raise ValueError("size must be >= 1")
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


async def gather_bounded(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R]],
    concurrency: int,
    *,
    return_exceptions: bool = False,
) -> list[R]:
    """Run ``worker`` over ``items`` with a bounded number of in-flight tasks.

    Args:
        items: Inputs to process.
        worker: Async function applied to each item.
        concurrency: Maximum simultaneous in-flight workers.
        return_exceptions: If True, exceptions are returned in place of results
            instead of propagating (mirrors ``asyncio.gather`` semantics).

    Returns:
        Results in the same order as ``items``.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    semaphore = asyncio.Semaphore(concurrency)
    materialized = list(items)

    async def _guarded(item: T) -> R:
        async with semaphore:
            return await worker(item)

    tasks = [asyncio.ensure_future(_guarded(item)) for item in materialized]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


async def process_in_batches(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    batch_size: int,
    concurrency: int,
    return_exceptions: bool = False,
) -> list[R]:
    """Process ``items`` batch-by-batch with bounded concurrency per batch.

    Chunking caps peak memory/connection use for very large inputs while the
    semaphore caps in-flight work within each chunk.
    """
    results: list[R] = []
    for batch in chunked(items, batch_size):
        batch_results = await gather_bounded(
            batch, worker, concurrency, return_exceptions=return_exceptions
        )
        results.extend(batch_results)
    return results
