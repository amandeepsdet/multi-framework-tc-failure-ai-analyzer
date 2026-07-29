"""Minimal pytest example.

Wire the PytestAdapter into a pytest hook so any failing test is analyzed.
Drop this into (or import it from) your ``conftest.py``.

Run the standalone demo:
    python examples/pytest/main.py
"""

from aiqa import FailureAnalyzer, render
from aiqa.adapters import PytestAdapter


def analyze_from_exception(exc: BaseException, test_name: str) -> None:
    # 1. FailureContext creation via the pytest adapter (plain-exception form)
    context = PytestAdapter().collect_failure_context(exception=exc, test_name=test_name)

    # 2. Analysis
    result = FailureAnalyzer().analyze(context)

    # 3. Report generation
    print(render(result, "console", context))


# --- Real pytest wiring (put in conftest.py) --------------------------------
# import pytest
#
# @pytest.hookimpl(hookwrapper=True)
# def pytest_runtest_makereport(item, call):
#     outcome = yield
#     report = outcome.get_result()
#     if report.when == "call" and report.failed:
#         context = PytestAdapter().collect_failure_context(
#             item=item, call=call, report=report
#         )
#         print(render(FailureAnalyzer().analyze(context), "console", context))


if __name__ == "__main__":
    try:
        assert False, "expected 200 but server returned HTTP 401 Unauthorized"
    except AssertionError as exc:
        analyze_from_exception(exc, test_name="auth::test_login")
