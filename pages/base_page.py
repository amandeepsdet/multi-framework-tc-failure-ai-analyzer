"""Base page object shared by all concrete pages.

Holds the Playwright ``Page`` handle plus common helpers (navigation,
screenshots, waiting) so concrete pages avoid duplicating boilerplate.
"""

from __future__ import annotations

from playwright.sync_api import Page

from utils.config import Config, config
from utils.helpers import screenshot_path
from utils.logger import get_logger


class BasePage:
    """Common behaviour inherited by every page object."""

    def __init__(self, page: Page, cfg: Config = config) -> None:
        self.page = page
        self.config = cfg
        self.log = get_logger(self.__class__.__name__)

    def goto(self, path: str = "") -> None:
        """Navigate to a path relative to the configured base URL."""
        url = f"{self.config.base_url}{path}"
        self.log.info("Navigating to %s", url)
        self.page.goto(url, wait_until="domcontentloaded")

    def capture(self, name: str) -> str:
        """Save a full-page screenshot and return its path."""
        path = screenshot_path(name)
        self.page.screenshot(path=path, full_page=True)
        self.log.info("Screenshot saved: %s", path)
        return path

    def dismiss_welcome_banner(self, timeout_ms: int = 3000) -> bool:
        """Dismiss the intermittent "Got it!" welcome overlay if present.

        ThingsBoard shows a welcome overlay (``welcome-container``) both after
        login and when first opening the Dashboards page. It intercepts pointer
        events, so we clear it before interacting. Best-effort: click when
        visible within a short window, otherwise ignore silently.
        """
        got_it = self.page.get_by_role("button", name="Got it!")
        try:
            got_it.wait_for(state="visible", timeout=timeout_ms)
            got_it.click()
            self.log.info("Dismissed 'Got it!' welcome overlay")
            # Wait for the overlay to detach so it no longer blocks clicks.
            try:
                self.page.locator(".welcome-container").wait_for(
                    state="hidden", timeout=timeout_ms
                )
            except Exception:  # noqa: BLE001 - overlay may already be gone
                pass
            return True
        except Exception:  # noqa: BLE001 - banner is optional; ignore if absent
            self.log.info("No 'Got it!' welcome overlay shown")
            return False
