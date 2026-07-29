"""Example: wire AIQA into pytest via a hook, for ANY test type.

Drop this into your ``conftest.py``. It analyses every failing test — UI, API,
or unit — using the framework-agnostic ``PytestAdapter``. No browser required.
"""

from __future__ import annotations

import pytest

from aiqa import FailureAnalyzer
from aiqa.adapters import PytestAdapter
from aiqa.reporting import ConsoleReporter

_analyzer = FailureAnalyzer()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        context = PytestAdapter().collect_failure_context(
            item=item, call=call, report=report, environment="ci"
        )
        result = _analyzer.analyze(context)
        # Print a one-line AI summary next to the failure.
        print("\n" + ConsoleReporter().summary_line(result, context))


if __name__ == "__main__":
    # Runnable demo without pytest objects, using a raw exception.
    from aiqa import render

    ctx = PytestAdapter().collect_failure_context(
        AssertionError("expected 200 but API returned status 503"),
        test_name="api::test_health",
    )
    print(render(_analyzer.analyze(ctx), "markdown", ctx))
