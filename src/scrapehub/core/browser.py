"""Playwright async headless browser manager.

Handles JS rendering, AJAX waits and infinite-scroll automation for the
quotes.toscrape.com ``/js`` and ``/scroll`` demos. Imports of Playwright are
deferred so the rest of the package (and the offline test suite) work even when
the browser driver is not installed.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from scrapehub.core.proxy_pool import ProxyPool
from scrapehub.core.user_agents import UserAgentRotator
from scrapehub.logging_setup import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from playwright.async_api import Browser, BrowserContext, Page

logger = get_logger(component="browser")


class BrowserManager:
    """Async context manager around a headless Chromium instance.

    Args:
        proxy_pool: Optional proxy pool; the first usable proxy is applied to the
            browser context (Playwright sets proxy per-context).
        ua_rotator: User-agent rotator for the context.
        headless: Run Chromium headless (always True in CI/Docker).
        timeout: Default navigation/selector timeout (ms derived from seconds).
    """

    def __init__(
        self,
        *,
        proxy_pool: ProxyPool | None = None,
        ua_rotator: UserAgentRotator | None = None,
        headless: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self._proxy_pool = proxy_pool or ProxyPool()
        self._ua = ua_rotator or UserAgentRotator()
        self._headless = headless
        self._timeout_ms = int(timeout * 1000)
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        """Launch Chromium and create a configured browser context."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)

        proxy = self._proxy_pool.get()
        context_kwargs: dict[str, Any] = {
            "user_agent": self._ua.next_agent(),
            "locale": "en-US",
            "viewport": {"width": 1366, "height": 768},
        }
        if proxy:
            context_kwargs["proxy"] = {"server": proxy}

        self._context = await self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self._timeout_ms)
        logger.info("browser.started", headless=self._headless, proxied=bool(proxy))

    async def new_page(self) -> Page:
        """Open a new page in the managed context."""
        if self._context is None:
            raise RuntimeError("BrowserManager not started")
        return await self._context.new_page()

    async def render(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        wait_until: str = "networkidle",
    ) -> str:
        """Navigate to ``url``, optionally wait for a selector, return HTML.

        Args:
            url: Target URL.
            wait_for_selector: CSS selector to await (ensures AJAX content
                has rendered before reading the DOM).
            wait_until: Playwright load state (``"networkidle"`` waits for AJAX).
        """
        page = await self.new_page()
        try:
            await page.goto(url, wait_until=wait_until)
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector)
            return await page.content()
        finally:
            await page.close()

    async def scroll_collect(
        self,
        url: str,
        *,
        item_selector: str,
        max_scrolls: int = 20,
        pause_ms: int = 400,
    ) -> str:
        """Drive infinite scroll until no new items load, return final HTML.

        Repeatedly scrolls to the bottom and waits for the item count to grow.
        Stops when the count stabilises or ``max_scrolls`` is hit.

        Args:
            url: Page implementing infinite scroll.
            item_selector: Selector counted to detect newly-loaded items.
            max_scrolls: Safety cap on scroll iterations.
            pause_ms: Delay after each scroll to let AJAX settle.
        """
        page = await self.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(item_selector)
            previous = -1
            for i in range(max_scrolls):
                count = await page.locator(item_selector).count()
                if count == previous:
                    logger.info("browser.scroll.stable", iterations=i, items=count)
                    break
                previous = count
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(pause_ms)
            return await page.content()
        finally:
            await page.close()

    async def stop(self) -> None:
        """Tear down context, browser and Playwright."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        logger.info("browser.stopped")
