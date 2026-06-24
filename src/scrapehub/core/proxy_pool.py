"""Rotating proxy pool with health tracking and failure cooldown.

The pool selects proxies round-robin or randomly, skips proxies that are in a
cooldown window after consecutive failures, and recovers them automatically once
the cooldown expires. It ships with *no* proxies: users supply their own.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class ProxyState:
    """Health bookkeeping for a single proxy URL."""

    url: str
    failures: int = 0
    successes: int = 0
    cooldown_until: float = 0.0

    def is_available(self, now: float) -> bool:
        return now >= self.cooldown_until


@dataclass
class ProxyPool:
    """A rotating pool of proxies with simple health management.

    Args:
        proxies: Proxy URLs (e.g. ``http://user:pass@host:port``).
        strategy: ``"round_robin"`` or ``"random"``.
        max_failures: Consecutive failures before a proxy is put on cooldown.
        cooldown_seconds: How long a tripped proxy stays unavailable.
        seed: Optional RNG seed for deterministic tests.
    """

    proxies: list[str] = field(default_factory=list)
    strategy: str = "round_robin"
    max_failures: int = 3
    cooldown_seconds: float = 30.0
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.strategy not in {"round_robin", "random"}:
            raise ValueError("strategy must be 'round_robin' or 'random'")
        self._states: dict[str, ProxyState] = {p: ProxyState(url=p) for p in self.proxies}
        self._order: list[str] = list(self.proxies)
        self._cursor = 0
        self._rng = random.Random(self.seed)

    @property
    def empty(self) -> bool:
        """True when no proxies are configured (direct connections)."""
        return not self._order

    def _now(self) -> float:
        return time.monotonic()

    def available(self) -> list[str]:
        """Return currently usable proxy URLs."""
        now = self._now()
        return [s.url for s in self._states.values() if s.is_available(now)]

    def get(self) -> str | None:
        """Return the next usable proxy, or ``None`` for a direct connection.

        Falls back to ``None`` when the pool is empty or every proxy is cooling
        down, so callers can degrade gracefully instead of failing hard.
        """
        if self.empty:
            return None
        usable = self.available()
        if not usable:
            return None
        if self.strategy == "random":
            return self._rng.choice(usable)
        # round-robin over the *available* set, preserving stable ordering
        for _ in range(len(self._order)):
            candidate = self._order[self._cursor % len(self._order)]
            self._cursor += 1
            if candidate in usable:
                return candidate
        return usable[0]

    def report_success(self, proxy: str | None) -> None:
        """Record a successful use; resets the failure counter."""
        if proxy is None:
            return
        state = self._states.get(proxy)
        if state is not None:
            state.successes += 1
            state.failures = 0
            state.cooldown_until = 0.0

    def report_failure(self, proxy: str | None) -> None:
        """Record a failure; trips cooldown once ``max_failures`` is reached."""
        if proxy is None:
            return
        state = self._states.get(proxy)
        if state is None:
            return
        state.failures += 1
        if state.failures >= self.max_failures:
            state.cooldown_until = self._now() + self.cooldown_seconds

    def stats(self) -> dict[str, dict[str, float]]:
        """Return a snapshot of per-proxy health for monitoring."""
        now = self._now()
        return {
            s.url: {
                "failures": s.failures,
                "successes": s.successes,
                "available": float(s.is_available(now)),
            }
            for s in self._states.values()
        }
