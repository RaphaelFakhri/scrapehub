"""Retry/backoff helpers built on ``tenacity``.

Provides a reusable async retry decorator with exponential backoff + jitter for
transient HTTP, network and timeout errors. Permanent errors (4xx other than
429) are *not* retried.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

T = TypeVar("T")

# Status codes worth retrying: rate limiting + transient server errors.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Network-level exceptions that indicate a transient failure.
TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


class RetryableHTTPStatusError(Exception):
    """Raised internally to signal a retryable HTTP status code."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"retryable status {status_code}")


def is_retryable_exception(exc: BaseException) -> bool:
    """Return True if ``exc`` represents a transient, retryable failure."""
    if isinstance(exc, RetryableHTTPStatusError):
        return True
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


def make_retrying(
    max_attempts: int = 4,
    initial: float = 0.5,
    max_wait: float = 10.0,
    on_retry: Callable[[RetryCallState], None] | None = None,
) -> AsyncRetrying:
    """Build a configured :class:`tenacity.AsyncRetrying` controller.

    Args:
        max_attempts: Total attempts (including the first).
        initial: Base backoff seconds.
        max_wait: Cap on backoff seconds.
        on_retry: Optional callback invoked before each sleep (e.g. metrics).
    """
    kwargs: dict[str, Any] = {
        "retry": retry_if_exception(is_retryable_exception),
        "stop": stop_after_attempt(max_attempts),
        "wait": wait_exponential_jitter(initial=initial, max=max_wait),
        "reraise": True,
    }
    if on_retry is not None:
        kwargs["before_sleep"] = on_retry
    return AsyncRetrying(**kwargs)
