"""Tests for CSV/JSON export with schema-driven columns."""

from __future__ import annotations

import csv
import json

from scrapehub.models.book import Book
from scrapehub.models.quote import Quote
from scrapehub.pipeline.export import export_csv, export_json, export_records


def _sample_books() -> list[Book]:
    return [
        Book(
            title="A",
            price=1.5,
            currency="£",
            rating=3,
            availability="In stock",
            in_stock=True,
            url="http://a",
        ),
        Book(
            title="B",
            price=2.0,
            currency="£",
            rating=5,
            availability="In stock",
            in_stock=True,
            url="http://b",
        ),
    ]


def test_export_csv_has_schema_columns(tmp_path):
    out = export_csv(_sample_books(), tmp_path / "books.csv", Book)
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == list(Book.model_fields.keys())
    assert rows[1][0] == "A"
    assert len(rows) == 3  # header + 2


def test_export_json_roundtrips(tmp_path):
    out = export_json(_sample_books(), tmp_path / "books.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["title"] == "A"


def test_export_csv_encodes_list_columns(tmp_path):
    quotes = [Quote(text="hi", author="x", tags=["a", "b"])]
    out = export_csv(quotes, tmp_path / "q.csv", Quote)
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    tags_index = list(Quote.model_fields.keys()).index("tags")
    assert json.loads(rows[1][tags_index]) == ["a", "b"]


def test_export_records_writes_both(tmp_path):
    paths = export_records(_sample_books(), tmp_path / "books", Book)
    assert paths["csv"].exists()
    assert paths["json"].exists()
    assert paths["csv"].suffix == ".csv"
    assert paths["json"].suffix == ".json"
