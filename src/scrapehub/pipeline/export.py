"""Export validated pydantic records to CSV and JSON.

Columns are derived from the model schema for stable, schema-driven ordering.
Lists/dicts are JSON-encoded in CSV cells so the file stays flat.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _columns(model: type[BaseModel]) -> list[str]:
    """Stable column order from the model's declared field order."""
    return list(model.model_fields.keys())


def _cell(value: Any) -> str:
    """Render a value as a CSV cell (JSON-encode containers)."""
    if value is None:
        return ""
    if isinstance(value, list | dict | tuple):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def export_csv(records: Sequence[BaseModel], path: str | Path, model: type[BaseModel]) -> Path:
    """Write ``records`` to a CSV file with schema-driven columns."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = _columns(model)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for record in records:
            data = record.model_dump()
            writer.writerow([_cell(data.get(col)) for col in columns])
    return out


def export_json(records: Sequence[BaseModel], path: str | Path) -> Path:
    """Write ``records`` to a pretty, UTF-8 JSON array."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in records]
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def export_records(
    records: Sequence[BaseModel],
    base_path: str | Path,
    model: type[BaseModel],
) -> dict[str, Path]:
    """Write both ``<base>.csv`` and ``<base>.json``.

    Args:
        records: Validated model instances.
        base_path: Path without extension (e.g. ``data/books``).
        model: The schema, used for CSV column ordering.

    Returns:
        Mapping ``{"csv": Path, "json": Path}``.
    """
    base = Path(base_path)
    csv_path = export_csv(records, base.with_suffix(".csv"), model)
    json_path = export_json(records, base.with_suffix(".json"))
    return {"csv": csv_path, "json": json_path}
