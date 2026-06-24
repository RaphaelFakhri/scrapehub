"""Structured logging via ``structlog``.

Provides JSON (production) or pretty console (development) rendering plus helpers
to bind per-run ``request_id`` and per-source context so every log line is
traceable to a scrape run and source.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

import structlog


def configure_logging(log_format: str = "console", log_level: str = "INFO") -> None:
    """Configure structlog + stdlib logging once at process start.

    Args:
        log_format: ``"json"`` for machine-readable output, ``"console"`` for
            human-friendly colourised output.
        log_level: Standard logging level name.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_log_keys_on_first_use=True,
    )


def get_logger(**initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with optional initial context."""
    return structlog.get_logger().bind(**initial_values)


def new_request_id() -> str:
    """Generate a short unique id for a single scrape run."""
    return uuid.uuid4().hex[:12]


def bind_run_context(request_id: str | None = None, **context: Any) -> str:
    """Bind a ``request_id`` (and extra context) into all subsequent log lines.

    Returns the request id used so the caller can report it.
    """
    rid = request_id or new_request_id()
    structlog.contextvars.bind_contextvars(request_id=rid, **context)
    return rid


def clear_run_context() -> None:
    """Clear bound context variables (call at end of a run)."""
    structlog.contextvars.clear_contextvars()
