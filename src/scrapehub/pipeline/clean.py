"""Normalization helpers used before validation.

Pure functions: whitespace collapsing, unicode normalization, currency parsing
and tag de-duplication. Kept dependency-free and side-effect-free so they are
trivially unit-testable.
"""

from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_CURRENCY_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_NON_DIGIT_PREFIX = re.compile(r"^[^\d\-+]*")


def normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace and strip ends."""
    return _WS_RE.sub(" ", value).strip()


def normalize_unicode(value: str, form: str = "NFKC") -> str:
    """Apply unicode normalization (default NFKC) for stable comparisons."""
    return unicodedata.normalize(form, value)


def parse_currency(value: str) -> tuple[float, str]:
    """Parse a price string into ``(amount, currency_symbol)``.

    Handles strings like ``"£51.77"``, ``"$ 1,299.00"`` or ``"USD 12"``. The
    currency portion is whatever non-numeric prefix precedes the number.

    Raises:
        ValueError: If no numeric component can be found.
    """
    cleaned = normalize_unicode(value).strip()
    match = _CURRENCY_RE.search(cleaned)
    if not match:
        raise ValueError(f"no numeric value in {value!r}")
    number = float(match.group(0).replace(",", ""))
    symbol = _NON_DIGIT_PREFIX.match(cleaned)
    currency = symbol.group(0).strip() if symbol else ""
    return number, currency or "GBP"


def dedupe_tags(tags: list[str]) -> list[str]:
    """Lowercase, strip and de-duplicate tags preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        cleaned = normalize_whitespace(tag).lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
