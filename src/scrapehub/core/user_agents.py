"""User-agent rotation and realistic header generation.

A small curated pool of modern desktop user-agents is rotated (round-robin or
random) and paired with a coherent set of accompanying headers to reduce naive
anti-bot fingerprinting. This is *politeness/realism*, not evasion.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator

# Curated, realistic, current-ish desktop user agents.
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
)


class UserAgentRotator:
    """Rotates user agents and emits matching header sets.

    Args:
        user_agents: Optional override pool (defaults to :data:`USER_AGENTS`).
        strategy: ``"round_robin"`` or ``"random"``.
        seed: Optional RNG seed for deterministic tests.
    """

    def __init__(
        self,
        user_agents: tuple[str, ...] | None = None,
        strategy: str = "round_robin",
        seed: int | None = None,
    ) -> None:
        if strategy not in {"round_robin", "random"}:
            raise ValueError("strategy must be 'round_robin' or 'random'")
        # ``None`` means "use defaults"; an explicit empty pool is an error.
        self._agents: tuple[str, ...] = tuple(USER_AGENTS if user_agents is None else user_agents)
        if not self._agents:
            raise ValueError("user_agents pool must not be empty")
        self._strategy = strategy
        self._rng = random.Random(seed)
        self._cycle: Iterator[str] = itertools.cycle(self._agents)

    def next_agent(self) -> str:
        """Return the next user-agent string per the chosen strategy."""
        if self._strategy == "random":
            return self._rng.choice(self._agents)
        return next(self._cycle)

    def headers(self, user_agent: str | None = None) -> dict[str, str]:
        """Return a coherent, realistic header set for a (chosen) user agent."""
        ua = user_agent or self.next_agent()
        is_firefox = "Firefox" in ua
        headers = {
            "User-Agent": ua,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if not is_firefox:
            # Chromium-family client hints.
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none"
            headers["Sec-Fetch-User"] = "?1"
        return headers
