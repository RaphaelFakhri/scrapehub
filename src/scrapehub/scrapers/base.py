"""Abstract base class defining the scraper lifecycle.

Every source scraper implements ``fetch`` (acquire raw payloads) and ``parse``
(turn payloads into raw dicts). The base ``run`` method threads those through the
shared clean -> validate pipeline and returns a structured result with metrics.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from scrapehub.core.metrics import Metrics
from scrapehub.logging_setup import get_logger
from scrapehub.pipeline.validate import ValidationReport, validate_records

M = TypeVar("M", bound=BaseModel)


@dataclass
class ScrapeResult(Generic[M]):
    """The output of a scraper run."""

    source: str
    records: list[M] = field(default_factory=list)
    report: ValidationReport | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


class BaseScraper(abc.ABC, Generic[M]):
    """Template-method base for all scrapers.

    Subclasses set :attr:`source` and :attr:`model` and implement
    :meth:`fetch` and :meth:`parse`. The shared :meth:`run` runs the
    fetch -> parse -> validate lifecycle and assembles a :class:`ScrapeResult`.
    """

    source: str = "base"
    model: type[BaseModel]

    def __init__(self, *, metrics: Metrics | None = None) -> None:
        self.metrics = metrics or Metrics()
        self.log = get_logger(source=self.source)

    @abc.abstractmethod
    async def fetch(self, **kwargs: Any) -> Any:
        """Acquire raw payload(s) from the source (HTML, JSON, ...)."""
        raise NotImplementedError

    @abc.abstractmethod
    def parse(self, raw: Any) -> list[dict]:
        """Turn raw payload(s) into a list of cleaned record dicts."""
        raise NotImplementedError

    def validate(self, records: list[dict]) -> ValidationReport:
        """Validate raw dicts against :attr:`model`, recording metrics."""
        report = validate_records(records, self.model)
        self.metrics.record_success(self.source, n=len(report.valid))
        self.metrics.record_failure(self.source, n=len(report.quarantined))
        if report.quarantined:
            self.log.warning(
                "scrape.quarantine",
                count=len(report.quarantined),
                examples=[q.reason for q in report.quarantined[:3]],
            )
        return report

    async def run(self, **kwargs: Any) -> ScrapeResult:
        """Execute the full fetch -> parse -> validate lifecycle."""
        self.log.info("scrape.start", **kwargs)
        raw = await self.fetch(**kwargs)
        records = self.parse(raw)
        report = self.validate(records)
        self.log.info("scrape.done", **report.summary())
        return ScrapeResult(
            source=self.source,
            records=list(report.valid),
            report=report,
            metrics=self.metrics.summary(),
        )
