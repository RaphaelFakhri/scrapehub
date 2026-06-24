"""Tests for the cleaning helpers and the validation stage."""

from __future__ import annotations

import pytest

from scrapehub.models.book import Book
from scrapehub.models.quote import Quote
from scrapehub.pipeline.clean import (
    dedupe_tags,
    normalize_unicode,
    normalize_whitespace,
    parse_currency,
)
from scrapehub.pipeline.validate import validate_records


def test_normalize_whitespace_collapses_runs():
    assert normalize_whitespace("  a\t b\n c ") == "a b c"


def test_normalize_unicode_nfkc():
    # Fullwidth digit -> ASCII under NFKC.
    assert normalize_unicode("１") == "1"


@pytest.mark.parametrize(
    "raw,amount,currency",
    [
        ("£51.77", 51.77, "£"),
        ("$ 1,299.00", 1299.0, "$"),
        ("USD 12", 12.0, "USD"),
    ],
)
def test_parse_currency(raw, amount, currency):
    parsed_amount, parsed_currency = parse_currency(raw)
    assert parsed_amount == pytest.approx(amount)
    assert parsed_currency == currency


def test_parse_currency_no_number_raises():
    with pytest.raises(ValueError):
        parse_currency("free")


def test_dedupe_tags_lowercases_and_orders():
    assert dedupe_tags(["Change", "change", " Deep "]) == ["change", "deep"]


def test_validate_records_partitions_valid_and_invalid():
    records = [
        {"text": "valid", "author": "A", "tags": ["x"]},
        {"text": "", "author": "B", "tags": []},  # empty text -> invalid
    ]
    report = validate_records(records, Quote)
    assert len(report.valid) == 1
    assert len(report.quarantined) == 1
    assert "text" in report.quarantined[0].reason


def test_validate_book_rating_out_of_range_quarantined():
    records = [
        {
            "title": "Bad",
            "price": 1.0,
            "rating": 9,  # > 5 invalid
            "availability": "In stock",
            "url": "http://x",
        }
    ]
    report = validate_records(records, Book)
    assert report.summary()["quarantined"] == 1


def test_quote_model_strips_typographic_quotes():
    q = Quote.model_validate({"text": "“hi”", "author": "x", "tags": []})
    assert q.text == "hi"
