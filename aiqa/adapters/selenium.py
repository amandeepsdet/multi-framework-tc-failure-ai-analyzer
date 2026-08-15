"""Selenium adapter.

Isolates Selenium-specific access (``driver.current_url``, ``page_source``,
screenshots, and browser log capture). Selenium is used via duck typing and
imported lazily, so this module imports cleanly without Selenium installed.
"""

from __future__ import annotations

from typing import Any

from ..core.models import ConsoleMessage, FailureContext
from .base import FailureContextBuilder, FrameworkAdapter, git_commit


class SeleniumAdapter(FrameworkAdapter):
    """Builds a :class:`FailureContext` from a Selenium ``WebDriver``."""

    name = "selenium"

    def __init__(self, driver: Any = None, *, dom_max_chars: int = 20000) -> None:
        self.driver = driver
        self.dom_max_chars = dom_max_chars

    def collect_failure_context(
        self,
        exception: BaseException | None = None,
        *,
        test_name: str,
        assertion_message: str = "",
        screenshot: str | None = None,
        api_responses: list[dict[str, Any]] | None = None,
        browser: str = "",
        environment: str = "",
        execution_time_s: float | None = None,
        **_: Any,
    ) -> FailureContext:
        builder = (
            FailureContextBuilder()
            .with_test(
                test_name,
                framework=self.name,
                execution_time_s=execution_time_s,
                git_commit=git_commit(),
            )
            .with_exception(exception)
            .with_assertion(assertion_message)
            .with_screenshot(screenshot)
            .with_execution(browser=browser, environment=environment)
        )
        if api_responses:
            builder.with_api_responses(api_responses)
        self._snapshot_driver(builder)
        return builder.build()

    def _snapshot_driver(self, builder: FailureContextBuilder) -> None:
        driver = self.driver
        if driver is None:
            return
        url = title = dom = ""
        try:
            url = driver.current_url
        except Exception:
            pass
        try:
            title = driver.title
        except Exception:
            pass
        try:
            dom = driver.page_source
        except Exception:
            pass
        builder.with_execution(url=url, page_title=title)
        if dom:
            builder.with_dom(dom, max_chars=self.dom_max_chars)
        # Browser console logs (only available on some drivers/configs).
        try:
            entries = driver.get_log("browser")
            builder.with_console(
                [
                    ConsoleMessage(
                        level=str(e.get("level", "log")).lower(), text=e.get("message", "")
                    )
                    for e in entries
                ]
            )
        except Exception:
            pass
