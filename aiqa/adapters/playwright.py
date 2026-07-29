"""Playwright adapter.

Isolates *all* Playwright-specific logic:

* :class:`PlaywrightEventRecorder` buffers console + network events from a live
  ``Page`` (these signals cannot be recovered after the fact).
* :class:`PlaywrightAdapter` snapshots URL, title, DOM, and screenshot at
  failure time and produces a generic :class:`FailureContext`.

Playwright is imported lazily (only its runtime objects are used via duck
typing), so importing this module never requires Playwright to be installed.
"""

from __future__ import annotations

from typing import Any

from ..core.models import ConsoleMessage, FailureContext, NetworkEvent
from .base import FailureContextBuilder, FrameworkAdapter, git_commit


class PlaywrightEventRecorder:
    """Buffers console + network events for a single Playwright ``Page``."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.console: list[ConsoleMessage] = []
        self.network: list[NetworkEvent] = []
        self._attach()

    def _attach(self) -> None:
        try:
            self.page.on("console", self._on_console)
            self.page.on("response", self._on_response)
            self.page.on("requestfailed", self._on_request_failed)
        except Exception:
            pass

    def _on_console(self, message: Any) -> None:
        try:
            self.console.append(ConsoleMessage(level=message.type, text=message.text))
        except Exception:
            pass

    def _on_response(self, response: Any) -> None:
        try:
            self.network.append(
                NetworkEvent(method=response.request.method, url=response.url, status=response.status)
            )
        except Exception:
            pass

    def _on_request_failed(self, request: Any) -> None:
        try:
            self.network.append(
                NetworkEvent(method=request.method, url=request.url,
                             response_body=str(getattr(request, "failure", "")))
            )
        except Exception:
            pass


class PlaywrightAdapter(FrameworkAdapter):
    """Builds a :class:`FailureContext` from a Playwright ``Page``."""

    name = "playwright"

    def __init__(self, page: Any = None, recorder: PlaywrightEventRecorder | None = None,
                 *, dom_max_chars: int = 20000) -> None:
        self.page = page
        self.recorder = recorder
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
                framework_version=self._framework_version(),
                execution_time_s=execution_time_s,
                git_commit=git_commit(),
            )
            .with_exception(exception)
            .with_assertion(assertion_message)
            .with_screenshot(screenshot)
            .with_execution(browser=browser, environment=environment)
        )
        if self.recorder is not None:
            builder.with_console(self.recorder.console).with_network(self.recorder.network)
        if api_responses:
            builder.with_api_responses(api_responses)
        self._snapshot_page(builder)
        return builder.build()

    # -- Playwright-specific snapshotting ----------------------------------- #
    def _snapshot_page(self, builder: FailureContextBuilder) -> None:
        page = self.page
        if page is None:
            return
        url = title = dom = ""
        try:
            url = page.url
        except Exception:
            pass
        try:
            title = page.title()
        except Exception:
            pass
        try:
            dom = page.content()
        except Exception:
            pass
        builder.with_execution(url=url, page_title=title)
        if dom:
            builder.with_dom(dom, max_chars=self.dom_max_chars)

    @staticmethod
    def _framework_version() -> str:
        try:
            from importlib.metadata import version

            return version("playwright")
        except Exception:
            return ""
