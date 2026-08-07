"""Example: analyze a Robot Framework failure with the AIQA SDK.

The ``RobotFrameworkAdapter`` turns keyword/test result values (available in a
listener or ``End Test`` hook) into a generic ``FailureContext``.

Run:
    python examples/robotframework_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import FailureAnalyzer, render
from aiqa.adapters import RobotFrameworkAdapter


def on_test_end(test_name: str, message: str, status: str) -> None:
    """Call this from a Robot listener's ``end_test`` when status == 'FAIL'."""
    context = RobotFrameworkAdapter().collect_failure_context(
        test_name=test_name,
        message=message,
        status=status,
        suite="Orders",
        tags=["smoke", "orders"],
        elapsed_s=2.4,
        environment="qa",
    )
    print(render(FailureAnalyzer().analyze(context), "markdown", context))


if __name__ == "__main__":
    on_test_end(
        test_name="Orders.Create Order",
        message="AssertionError: expected 200 but the API returned HTTP 500",
        status="FAIL",
    )
