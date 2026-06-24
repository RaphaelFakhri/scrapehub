"""Versioned selector registry with fallbacks for resilience."""

from __future__ import annotations

from scrapehub.selectors.registry import SELECTORS, SelectorSet, select_one, select_text

__all__ = ["SELECTORS", "SelectorSet", "select_one", "select_text"]
