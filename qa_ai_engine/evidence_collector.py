"""Failure evidence collection from Playwright pages, exceptions, and context.

Two responsibilities:

1. :class:`PageEventRecorder` — attached to a Playwright ``Page`` at test start
   (via an autouse fixture) so console messages and network exchanges are
   buffered live. Console/network signals cannot be recovered after the fact,
   hence the recorder.
2. :class:`EvidenceCollector` — at failure time, snapshots URL, title, DOM,
   screenshot, stacktrace, API responses, and rich test metadata into a single
   :class:`~ai.models.Evidence` / :class:`~ai.models.FailureRecord`.

All collection is best-effort and defensive: a browser already closed, a locked
file, or a missing git binary must never turn a test failure into a crash.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from typing import Any

from ._logging import get_logger
from .ai_config import AIConfig, ai_config
from .models import Evidence, FailureRecord, NetworkRecord, TestMetadata

logger = get_logger("ai.evidence_collector")


class PageEventRecorder:
    """Buffers console + network events for a single Playwright page."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.console: list[dict[str, Any]] = []
        self.network: list[dict[str, Any]] = []
        self._attach()

    def _attach(self) -> None:
        try:
            self.page.on("console", self._on_console)
            self.page.on("response", self._on_response)
            self.page.on("requestfailed", self._on_request_failed)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not attach page recorders: %s", exc)

    def _on_console(self, message: Any) -> None:
        try:
            self.console.append({"type": message.type, "text": message.text})
        except Exception:  # pragma: no cover
            pass

    def _on_response(self, response: Any) -> None:
        try:
            request = response.request
            self.network.append(
                NetworkRecord(
                    method=request.method,
                    url=response.url,
                    status=response.status,
                ).to_dict()
            )
        except Exception:  # pragma: no cover
            pass

    def _on_request_failed(self, request: Any) -> None:
        try:
            self.network.append(
                NetworkRecord(
                    method=request.method,
                    url=request.url,
                    status=None,
                    response_body=str(getattr(request, "failure", "")),
                ).to_dict()
            )
        except Exception:  # pragma: no cover
            pass

    def errors(self) -> list[dict[str, Any]]:
        return [c for c in self.console if c.get("type") in {"error", "warning"}]


class EvidenceCollector:
    """Assembles a :class:`FailureRecord` from all available signals."""

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------- page state
    def collect_from_page(self, page: Any) -> dict[str, Any]:
        """Snapshot URL, title, and DOM from a live page (best effort)."""
        data: dict[str, Any] = {"url": "", "page_title": "", "dom": ""}
        if page is None:
            return data
        try:
            data["url"] = page.url
        except Exception:  # pragma: no cover
            pass
        try:
            data["page_title"] = page.title()
        except Exception:  # pragma: no cover
            pass
        try:
            dom = page.content()
            data["dom"] = dom[: self.cfg.dom_max_chars]
        except Exception:  # pragma: no cover
            pass
        return data

    # ------------------------------------------------------------- exceptions
    @staticmethod
    def format_exception(exc: BaseException | None) -> dict[str, str]:
        if exc is None:
            return {"exception_type": "", "exception_message": "", "stacktrace": ""}
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "stacktrace": stack,
        }

    # -------------------------------------------------------------- metadata
    def build_metadata(
        self, test_name: str, browser: str = "", execution_time_s: float | None = None
    ) -> TestMetadata:
        return TestMetadata(
            test_name=test_name,
            browser=browser,
            environment=self._environment(),
            timestamp=datetime.now(UTC).isoformat(),
            execution_time_s=execution_time_s,
            os=f"{platform.system()} {platform.release()}",
            python_version=platform.python_version(),
            git_commit=self._git_commit(),
            framework_version=self.cfg.framework_version,
        )

    @staticmethod
    def _environment() -> str:
        import os

        return os.getenv("TEST_ENV", os.getenv("AIQA_ENV", "default"))

    @staticmethod
    def _git_commit() -> str:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:  # pragma: no cover - git may be absent
            return ""

    # -------------------------------------------------------------- assembly
    def build_record(
        self,
        *,
        test_name: str,
        exception: BaseException | None = None,
        page: Any = None,
        recorder: PageEventRecorder | None = None,
        screenshot: str | None = None,
        assertion_message: str = "",
        api_responses: list[dict[str, Any]] | None = None,
        browser: str = "",
        execution_time_s: float | None = None,
        trace_path: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> FailureRecord:
        """Gather every signal into a single structured :class:`FailureRecord`."""
        exc_info = self.format_exception(exception)
        page_state = self.collect_from_page(page) if self.cfg.collect_evidence else {}

        evidence = Evidence(
            screenshot=screenshot,
            stacktrace=exc_info["stacktrace"],
            exception_type=exc_info["exception_type"],
            exception_message=exc_info["exception_message"],
            assertion_message=assertion_message or exc_info["exception_message"],
            url=page_state.get("url", ""),
            page_title=page_state.get("page_title", ""),
            dom=page_state.get("dom", ""),
            console_logs=(recorder.console if recorder else []),
            network=(recorder.network if recorder else []),
            api_responses=api_responses or [],
            trace_path=trace_path,
        )
        metadata = self.build_metadata(test_name, browser, execution_time_s)
        return FailureRecord(
            test_name=test_name,
            failure=exc_info["exception_message"] or assertion_message,
            evidence=evidence,
            metadata=metadata,
            config=config_snapshot or self._default_config_snapshot(),
        )

    def _default_config_snapshot(self) -> dict[str, Any]:
        try:
            from utils.config import config as fw

            return {
                "timeout_ms": fw.default_timeout_ms,
                "poll_retries": fw.poll_retries,
                "api_retries": fw.api_retries,
                "dashboard_name": fw.dashboard_name,
                "base_url": fw.base_url,
            }
        except Exception:  # pragma: no cover
            return {}


# Convenience module-level singleton.
_collector = EvidenceCollector()


def current_python() -> str:
    return sys.version.split()[0]
