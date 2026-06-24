"""Lightweight in-process metrics for failure monitoring.

Tracks success / retry / failure counters per source so runs can surface a
machine-readable summary in structured logs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SourceCounters:
    """Per-source counters."""

    success: int = 0
    retry: int = 0
    failure: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"success": self.success, "retry": self.retry, "failure": self.failure}


@dataclass
class Metrics:
    """Aggregates counters across sources for a single run."""

    _counters: dict[str, SourceCounters] = field(
        default_factory=lambda: defaultdict(SourceCounters)
    )

    def record_success(self, source: str, n: int = 1) -> None:
        self._counters[source].success += n

    def record_retry(self, source: str, n: int = 1) -> None:
        self._counters[source].retry += n

    def record_failure(self, source: str, n: int = 1) -> None:
        self._counters[source].failure += n

    def summary(self) -> dict[str, dict[str, int]]:
        """Return a per-source snapshot of all counters."""
        return {source: c.as_dict() for source, c in self._counters.items()}

    def totals(self) -> dict[str, int]:
        """Return aggregate totals across every source."""
        total = SourceCounters()
        for c in self._counters.values():
            total.success += c.success
            total.retry += c.retry
            total.failure += c.failure
        return total.as_dict()
