"""Robot Framework adapter.

Builds a :class:`FailureContext` from Robot Framework result data (a keyword or
test failure message and status). Designed to be called from a Robot listener
(v3 API) or from post-run ``output.xml`` parsing. Robot Framework is not
imported here; the adapter accepts plain values.
"""

from __future__ import annotations

from typing import Any

from ..core.models import FailureContext
from .base import FailureContextBuilder, FrameworkAdapter, git_commit


class RobotFrameworkAdapter(FrameworkAdapter):
    """Builds a :class:`FailureContext` from Robot Framework result values."""

    name = "robotframework"

    def collect_failure_context(
        self,
        *,
        test_name: str,
        message: str = "",
        status: str = "FAIL",
        suite: str = "",
        tags: list[str] | None = None,
        elapsed_s: float | None = None,
        screenshot: str | None = None,
        environment: str = "",
        exception_type: str = "AssertionError",
        **_: Any,
    ) -> FailureContext:
        builder = (
            FailureContextBuilder()
            .with_test(
                test_name,
                suite=suite,
                framework=self.name,
                tags=list(tags or []),
                execution_time_s=elapsed_s,
                git_commit=git_commit(),
            )
            .with_exception_text(type=exception_type, message=message, stacktrace=message)
            .with_assertion(message)
            .with_screenshot(screenshot)
            .with_execution(environment=environment)
            .with_custom_evidence("robot_status", status)
        )
        return builder.build()
