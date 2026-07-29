"""pytest adapter.

Builds a :class:`FailureContext` from a pytest test-report / call context. This
adapter deals only with pytest's own objects (item, call, report) — no browser
or UI framework — so it works for API, unit, and integration tests alike.

pytest is imported lazily; nothing here requires a live browser.
"""

from __future__ import annotations

from typing import Any

from ..core.models import FailureContext
from .base import FailureContextBuilder, FrameworkAdapter, git_commit


class PytestAdapter(FrameworkAdapter):
    """Builds a :class:`FailureContext` from pytest report objects."""

    name = "pytest"

    def collect_failure_context(
        self,
        exception: BaseException | None = None,
        *,
        test_name: str = "",
        item: Any = None,
        call: Any = None,
        report: Any = None,
        assertion_message: str = "",
        api_responses: list[dict[str, Any]] | None = None,
        environment: str = "",
        **_: Any,
    ) -> FailureContext:
        name = test_name or self._nodeid(item, report)
        exc = exception or self._exc_from_call(call)
        message = assertion_message or self._longrepr(report)
        duration = getattr(report, "duration", None)
        tags = self._markers(item)

        builder = (
            FailureContextBuilder()
            .with_test(
                name,
                framework=self.name,
                framework_version=self._pytest_version(),
                tags=tags,
                execution_time_s=duration,
                git_commit=git_commit(),
            )
            .with_exception(exc)
            .with_assertion(message)
            .with_execution(environment=environment)
        )
        if api_responses:
            builder.with_api_responses(api_responses)
        return builder.build()

    # -- pytest object extraction ------------------------------------------ #
    @staticmethod
    def _nodeid(item: Any, report: Any) -> str:
        return getattr(item, "nodeid", None) or getattr(report, "nodeid", "") or "unknown"

    @staticmethod
    def _exc_from_call(call: Any) -> BaseException | None:
        excinfo = getattr(call, "excinfo", None)
        return getattr(excinfo, "value", None) if excinfo else None

    @staticmethod
    def _longrepr(report: Any) -> str:
        longrepr = getattr(report, "longrepr", None)
        return str(longrepr) if longrepr else ""

    @staticmethod
    def _markers(item: Any) -> list[str]:
        try:
            return [m.name for m in item.iter_markers()]
        except Exception:
            return []

    @staticmethod
    def _pytest_version() -> str:
        try:
            import pytest

            return getattr(pytest, "__version__", "")
        except Exception:
            return ""
