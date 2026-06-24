"""scrapehub: async headless scraping framework for sanctioned data sources.

Public API surface re-exports the most commonly used entrypoints so callers can
``from scrapehub import get_settings, configure_logging`` without spelunking.
"""

from __future__ import annotations

__version__ = "0.1.0"

from scrapehub.config import Settings, get_settings
from scrapehub.logging_setup import configure_logging, get_logger

__all__ = [
    "__version__",
    "Settings",
    "get_settings",
    "configure_logging",
    "get_logger",
]
