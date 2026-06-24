"""Pydantic v2 output schemas for each source."""

from __future__ import annotations

from scrapehub.models.article import Article
from scrapehub.models.book import Book
from scrapehub.models.quote import Quote
from scrapehub.models.story import Story

__all__ = ["Article", "Book", "Quote", "Story"]
