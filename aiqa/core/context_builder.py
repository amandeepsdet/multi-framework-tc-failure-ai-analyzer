"""Fluent builder for assembling a :class:`FailureContext`.

Adapters use this to construct a context incrementally from whatever evidence a
given framework exposes, without needing to know the internal shape of the core
models. It performs light normalisation (exception formatting, host metadata)
but contains **no** framework or application knowledge.
"""

from __future__ import annotations

import platform
import traceback
from typing import Any

from .models import (
    ConsoleMessage,
    Evidence,
    ExceptionInfo,
    ExecutionContext,
    FailureContext,
    FailureMetadata,
    LogEntry,
    NetworkEvent,
)


class FailureContextBuilder:
    """Incrementally assembles a :class:`FailureContext` (framework-agnostic)."""

    def __init__(self) -> None:
        self._metadata = FailureMetadata()
        self._exception = ExceptionInfo()
        self._evidence = Evidence()
        self._execution = ExecutionContext(
            os=f"{platform.system()} {platform.release()}",
            platform=platform.platform(),
        )
        self._assertion_message = ""

    # -- identity ----------------------------------------------------------- #
    def with_test(
        self,
        name: str,
        *,
        test_id: str = "",
        suite: str = "",
        framework: str = "",
        framework_version: str = "",
        tags: list[str] | None = None,
        execution_time_s: float | None = None,
        git_commit: str = "",
        retries: int = 0,
    ) -> FailureContextBuilder:
        self._metadata = FailureMetadata(
            test_id=test_id or name,
            test_name=name,
            suite=suite,
            framework=framework,
            framework_version=framework_version,
            tags=list(tags or []),
            execution_time_s=execution_time_s,
            git_commit=git_commit,
            retries=retries,
        )
        return self

    # -- failure signal ----------------------------------------------------- #
    def with_exception(self, exc: BaseException | None) -> FailureContextBuilder:
        if exc is not None:
            self._exception = ExceptionInfo(
                type=type(exc).__name__,
                message=str(exc),
                stacktrace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            )
        return self

    def with_exception_text(
        self, *, type: str = "", message: str = "", stacktrace: str = ""
    ) -> FailureContextBuilder:
        self._exception = ExceptionInfo(type=type, message=message, stacktrace=stacktrace)
        return self

    def with_assertion(self, message: str) -> FailureContextBuilder:
        self._assertion_message = message or ""
        return self

    # -- evidence ----------------------------------------------------------- #
    def with_screenshot(self, path: str | None) -> FailureContextBuilder:
        self._evidence.screenshot = path
        return self

    def with_dom(self, snapshot: str, *, max_chars: int = 20000) -> FailureContextBuilder:
        self._evidence.dom_snapshot = (snapshot or "")[:max_chars]
        return self

    def with_console(self, messages: list[Any]) -> FailureContextBuilder:
        for m in messages or []:
            if isinstance(m, ConsoleMessage):
                self._evidence.console.append(m)
            elif isinstance(m, dict):
                self._evidence.console.append(
                    ConsoleMessage(
                        level=m.get("level") or m.get("type") or "log", text=m.get("text", "")
                    )
                )
            else:
                self._evidence.console.append(ConsoleMessage(text=str(m)))
        return self

    def with_network(self, events: list[Any]) -> FailureContextBuilder:
        for e in events or []:
            if isinstance(e, NetworkEvent):
                self._evidence.network.append(e)
            elif isinstance(e, dict):
                known = {k: e[k] for k in NetworkEvent.__dataclass_fields__ if k in e}
                self._evidence.network.append(NetworkEvent(**known))
        return self

    def with_api_responses(self, responses: list[dict[str, Any]]) -> FailureContextBuilder:
        self._evidence.api_responses.extend(responses or [])
        return self

    def with_logs(self, logs: list[Any]) -> FailureContextBuilder:
        for entry in logs or []:
            if isinstance(entry, LogEntry):
                self._evidence.logs.append(entry)
            elif isinstance(entry, dict):
                known = {k: entry[k] for k in LogEntry.__dataclass_fields__ if k in entry}
                self._evidence.logs.append(LogEntry(**known))
            else:
                self._evidence.logs.append(LogEntry(message=str(entry)))
        return self

    def with_artifact(self, name: str, path: str) -> FailureContextBuilder:
        self._evidence.artifacts[name] = path
        return self

    def with_custom_evidence(self, key: str, value: Any) -> FailureContextBuilder:
        self._evidence.custom[key] = value
        return self

    # -- execution context -------------------------------------------------- #
    def with_execution(
        self,
        *,
        environment: str | None = None,
        browser: str | None = None,
        url: str | None = None,
        page_title: str | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> FailureContextBuilder:
        if environment is not None:
            self._execution.environment = environment
        if browser is not None:
            self._execution.browser = browser
        if url is not None:
            self._execution.url = url
        if page_title is not None:
            self._execution.page_title = page_title
        if configuration is not None:
            self._execution.configuration.update(configuration)
        return self

    # -- finalise ----------------------------------------------------------- #
    def build(self) -> FailureContext:
        assertion = self._assertion_message or self._exception.message
        return FailureContext(
            metadata=self._metadata,
            exception=self._exception,
            evidence=self._evidence,
            execution=self._execution,
            assertion_message=assertion,
        )
