"""Tests for retry classification and the AsyncHttpClient retry loop."""

from __future__ import annotations

import httpx
import pytest

from scrapehub.core.retry import (
    RetryableHTTPStatusError,
    is_retryable_exception,
    make_retrying,
)


def test_transient_network_errors_are_retryable():
    assert is_retryable_exception(httpx.ConnectError("boom"))
    assert is_retryable_exception(httpx.ReadTimeout("slow"))


def test_retryable_status_error_is_retryable():
    assert is_retryable_exception(RetryableHTTPStatusError(503))


def test_permanent_status_is_not_retryable():
    request = httpx.Request("GET", "https://x")
    response = httpx.Response(404, request=request)
    err = httpx.HTTPStatusError("nf", request=request, response=response)
    assert is_retryable_exception(err) is False


def test_429_status_error_is_retryable():
    request = httpx.Request("GET", "https://x")
    response = httpx.Response(429, request=request)
    err = httpx.HTTPStatusError("rl", request=request, response=response)
    assert is_retryable_exception(err) is True


@pytest.mark.asyncio
async def test_make_retrying_retries_until_success():
    attempts = {"n": 0}
    retrying = make_retrying(max_attempts=4, initial=0.0, max_wait=0.0)

    async for attempt in retrying:
        with attempt:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RetryableHTTPStatusError(503)
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_client_retries_then_succeeds(make_client):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with make_client(transport, max_retries=5) as client:
        data = await client.get_json("https://example.com/api")
    assert data == {"ok": True}
    assert calls["n"] == 3
    assert client.metrics.totals()["retry"] == 2


@pytest.mark.asyncio
async def test_client_raises_after_exhausting_retries(make_client):
    transport = httpx.MockTransport(lambda req: httpx.Response(503))
    async with make_client(transport, max_retries=2) as client:
        with pytest.raises(RetryableHTTPStatusError):
            await client.get_json("https://example.com/api")
