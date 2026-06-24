"""Verify that fallback selectors recover parsing when primary markup changes."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scrapehub.scrapers.quotes_static import parse_quotes_html
from scrapehub.selectors.registry import SelectorSet, select_text


def test_fallback_used_when_primary_missing():
    html = "<div><p class='legacy'>hello</p></div>"
    soup = BeautifulSoup(html, "lxml")
    selectors = SelectorSet(primary="p.modern", fallbacks=("p.legacy",))
    assert select_text(soup, selectors) == "hello"


def test_primary_preferred_over_fallback():
    html = "<div><p class='modern'>new</p><p class='legacy'>old</p></div>"
    soup = BeautifulSoup(html, "lxml")
    selectors = SelectorSet(primary="p.modern", fallbacks=("p.legacy",))
    assert select_text(soup, selectors) == "new"


def test_default_when_nothing_matches():
    soup = BeautifulSoup("<div></div>", "lxml")
    selectors = SelectorSet(primary="p.x", fallbacks=("p.y",))
    assert select_text(soup, selectors, default="N/A") == "N/A"


def test_quotes_parse_survives_renamed_text_class():
    """Simulate the site renaming span.text but keeping itemprop fallback."""
    html = """
    <div class="quote">
      <span itemprop="text">“Resilient extraction.”</span>
      <small class="author">Tester</small>
      <div class="tags"><a class="tag">resilience</a></div>
    </div>
    """
    records = parse_quotes_html(html)
    assert len(records) == 1
    # text selector primary 'span.text' missed; fallback "[itemprop='text']" matched.
    assert "Resilient extraction" in records[0]["text"]
    assert records[0]["author"] == "Tester"
    assert records[0]["tags"] == ["resilience"]
