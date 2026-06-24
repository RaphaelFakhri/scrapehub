"""Validation stage: run raw dicts through a pydantic schema.

Invalid rows are quarantined with a human-readable reason rather than aborting
the whole run, so a few bad records never sink an otherwise good scrape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


@dataclass
class QuarantinedRecord:
    """A record that failed validation, with the reason and original data."""

    reason: str
    data: dict


@dataclass
class ValidationReport:
    """Outcome of validating a batch of records."""

    valid: list[BaseModel] = field(default_factory=list)
    quarantined: list[QuarantinedRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.quarantined)

    def summary(self) -> dict[str, int]:
        return {
            "total": self.total,
            "valid": len(self.valid),
            "quarantined": len(self.quarantined),
        }


def validate_records(records: list[dict], model: type[M]) -> ValidationReport:
    """Validate ``records`` against ``model``.

    Args:
        records: Raw, cleaned dictionaries.
        model: A pydantic ``BaseModel`` subclass.

    Returns:
        A :class:`ValidationReport` partitioning valid and quarantined rows.
    """
    report = ValidationReport()
    for raw in records:
        try:
            report.valid.append(model.model_validate(raw))
        except ValidationError as exc:
            messages = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            report.quarantined.append(QuarantinedRecord(reason=messages, data=raw))
    return report
