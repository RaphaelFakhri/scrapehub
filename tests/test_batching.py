"""Tests for async batching with bounded concurrency."""

from __future__ import annotations

import asyncio

import pytest

from scrapehub.core.batching import chunked, gather_bounded, process_in_batches


def test_chunked_splits_evenly_and_remainder():
    assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_chunked_invalid_size():
    with pytest.raises(ValueError):
        chunked([1], 0)


@pytest.mark.asyncio
async def test_gather_bounded_preserves_order():
    async def worker(x: int) -> int:
        await asyncio.sleep(0)
        return x * 2

    result = await gather_bounded(range(5), worker, concurrency=2)
    assert result == [0, 2, 4, 6, 8]


@pytest.mark.asyncio
async def test_concurrency_is_bounded():
    state = {"current": 0, "peak": 0}

    async def worker(_x: int) -> int:
        state["current"] += 1
        state["peak"] = max(state["peak"], state["current"])
        await asyncio.sleep(0.01)
        state["current"] -= 1
        return _x

    await gather_bounded(range(20), worker, concurrency=4)
    assert state["peak"] <= 4


@pytest.mark.asyncio
async def test_return_exceptions_captures_errors():
    async def worker(x: int) -> int:
        if x == 2:
            raise ValueError("bad")
        return x

    results = await gather_bounded(range(4), worker, concurrency=2, return_exceptions=True)
    assert results[0] == 0
    assert isinstance(results[2], ValueError)


@pytest.mark.asyncio
async def test_process_in_batches_covers_all_items():
    async def worker(x: int) -> int:
        return x + 1

    result = await process_in_batches(list(range(10)), worker, batch_size=3, concurrency=2)
    assert result == list(range(1, 11))
