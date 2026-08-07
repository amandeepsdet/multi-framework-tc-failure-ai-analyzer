"""Example: analyze a plain Python failure — no test framework at all.

Any script, job, or service that raises an exception can be analyzed. Here we
simply ``try/except`` a call and hand the exception to the SDK via the pytest
adapter's plain-exception form (no pytest objects required).

Run:
    python examples/plain_python_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import FailureAnalyzer, render
from aiqa.adapters import PytestAdapter


def do_work() -> None:
    # Pretend this talks to a service that is momentarily unavailable.
    raise ConnectionError("HTTPSConnectionPool: Max retries exceeded (connection timed out)")


def main() -> None:
    try:
        do_work()
    except Exception as exc:  # noqa: BLE001 - demo: analyze whatever failed
        context = PytestAdapter().collect_failure_context(
            exception=exc, test_name="jobs::nightly_sync"
        )
        result = FailureAnalyzer().analyze(context)
        print(render(result, "console", context))


if __name__ == "__main__":
    main()
