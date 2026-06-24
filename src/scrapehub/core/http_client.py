"""Async HTTP client wiring together proxy rotation, UA rotation, polite
rate-limiting and retry/backoff.

This is the workhorse for API-style scraping (Wikipedia REST, Hacker News
Firebase). Browser-rendered sources use :mod:`scrapehub.core.browser` instead.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from scrapehub.core.metrics import Metrics
from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.rate_limiter import RateLimiter
from scrapehub.core.retry import RetryableHTTPStatusError, make_retrying
from scrapehub.core.user_agents import UserAgentRotator
from scrapehub.logging_setup import get_logger

logger = get_logger(component="http_client")


class AsyncHttpClient:
    """Resilient async HTTP client.

    Each request:
      1. waits on the per-host rate limiter,
      2. picks a proxy from the pool (or direct),
      3. attaches a rotated user-agent + realistic headers,
      4. is retried with exponential backoff + jitter on transient failures.

    Args:
        proxy_pool: Rotating proxy pool (may be empty for direct connections).
        ua_rotator: User-agent rotator.
        rate_limiter: Per-host token-bucket limiter.
        timeout: Request timeout (seconds).
        max_retries: Total attempts per request.
        metrics: Optional metrics sink.
        source: Source label used for metrics.
        transport: Optional httpx transport (tests inject a mock here).
    """

    def __init__(
        self,
        *,
        proxy_pool: ProxyPool | None = None,
        ua_rotator: UserAgentRotator | None = None,
        rate_limiter: RateLimiter | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        metrics: Metrics | None = None,
        source: str = "http",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._proxy_pool = proxy_pool or ProxyPool()
        self._ua = ua_rotator or UserAgentRotator()
        self._rate_limiter = rate_limiter or RateLimiter(rate=4.0)
        self._timeout = timeout
        self._max_retries = max_retries
        self._metrics = metrics or Metrics()
        self._source = source
        self._transport = transport
        # Cache one client per proxy URL (key ``""`` == direct).
        self._clients: dict[str, httpx.AsyncClient] = {}

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _client_for(self, proxy: str | None) -> httpx.AsyncClient:
        key = proxy or ""
        client = self._clients.get(key)
        if client is None:
            client = httpx.AsyncClient(
                proxy=proxy,
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=True,
            )
            self._clients[key] = client
        return client

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Perform a request with full resilience (rate-limit/proxy/UA/retry)."""

        def _on_retry(state: Any) -> None:
            self._metrics.record_retry(self._source)
            logger.warning(
                "request.retry",
                url=url,
                attempt=state.attempt_number,
                outcome=repr(state.outcome.exception()) if state.outcome else None,
            )

        retrying = make_retrying(max_attempts=self._max_retries, on_retry=_on_retry)

        async for attempt in retrying:
            with attempt:
                await self._rate_limiter.acquire(url)
                proxy = self._proxy_pool.get()
                headers = {**self._ua.headers(), **kwargs.pop("headers", {})}
                client = self._client_for(proxy)
                try:
                    response = await client.request(method, url, headers=headers, **kwargs)
                except Exception:
                    self._proxy_pool.report_failure(proxy)
                    raise
                if response.status_code in {429, 500, 502, 503, 504}:
                    self._proxy_pool.report_failure(proxy)
                    raise RetryableHTTPStatusError(response.status_code)
                self._proxy_pool.report_success(proxy)
                self._metrics.record_success(self._source)
                return response
        # AsyncRetrying with reraise=True will raise before reaching here.
        raise RuntimeError("unreachable: retry loop exited without result")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET and parse JSON, raising for non-2xx after retries are exhausted."""
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_text(self, url: str, **kwargs: Any) -> str:
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        return response.text

    @property
    def metrics(self) -> Metrics:
        return self._metrics

    async def aclose(self) -> None:
        """Close all underlying httpx clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
