"""Central, versioned CSS selector registry with fallbacks.

Every parser pulls selectors from here instead of hard-coding them. Each logical
field maps to a *list* of CSS selectors tried in order, so when a site's primary
markup changes, a fallback can keep parsing working. This is the resilience
mechanism exercised by ``tests/test_selectors_resilience.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class SelectorSet:
    """An ordered set of CSS selectors for one logical field.

    Args:
        primary: The preferred selector.
        fallbacks: Alternatives tried in order if ``primary`` misses.
    """

    primary: str
    fallbacks: tuple[str, ...] = ()

    @property
    def candidates(self) -> tuple[str, ...]:
        return (self.primary, *self.fallbacks)


def select_one(node: Tag | BeautifulSoup, selectors: SelectorSet) -> Tag | None:
    """Return the first element matching any candidate selector, else ``None``."""
    for css in selectors.candidates:
        found = node.select_one(css)
        if found is not None:
            return found
    return None


def select_text(
    node: Tag | BeautifulSoup,
    selectors: SelectorSet,
    *,
    default: str = "",
    attr: str | None = None,
) -> str:
    """Return text (or an attribute) from the first matching selector.

    Args:
        node: Root element to search within.
        selectors: Ordered selector set with fallbacks.
        default: Value returned when nothing matches.
        attr: If given, return this attribute instead of the element text.
    """
    el = select_one(node, selectors)
    if el is None:
        return default
    if attr is not None:
        value = el.get(attr)
        if value is None:
            return default
        return value if isinstance(value, str) else " ".join(value)
    return el.get_text(strip=True)


# --- Registry -----------------------------------------------------------------
# Version bump this when selectors change so logs can correlate parser versions.
REGISTRY_VERSION = "2026.06"

SELECTORS: dict[str, dict[str, SelectorSet]] = {
    "books": {
        # books.toscrape.com product listing
        "product": SelectorSet("article.product_pod", ("li article.product_pod", ".product_pod")),
        "title": SelectorSet("h3 a", ("h3 > a", ".product_pod h3 a")),
        "price": SelectorSet("p.price_color", (".price_color", "div.product_price .price_color")),
        "rating": SelectorSet("p.star-rating", (".star-rating",)),
        "availability": SelectorSet("p.instock.availability", (".availability", "p.availability")),
        "next_page": SelectorSet("li.next a", (".next a", "ul.pager .next a")),
    },
    "quotes": {
        # quotes.toscrape.com (static, /js and /scroll share markup)
        "quote": SelectorSet("div.quote", (".quote",)),
        "text": SelectorSet("span.text", (".text", "[itemprop='text']")),
        "author": SelectorSet("small.author", (".author", "[itemprop='author']")),
        "tags": SelectorSet("div.tags a.tag", (".tags .tag", "a.tag")),
        "next_page": SelectorSet("li.next a", (".next a", "ul.pager .next a")),
    },
}
