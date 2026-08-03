"""Generate the AIQA Quality Intelligence portal (reports/index.html).

Runs several simulated executions through the QualityPortal so the landing
dashboard shows real history, a knowledge base, and trend sparklines (trends
need >= 2-3 runs to be meaningful).

Usage (from the project root):

    .\\.venv\\Scripts\\python.exe examples\\generate_portal.py

Then open reports/index.html in a browser.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import FailureAnalyzer, FailureContextBuilder
from aiqa.reporting import QualityPortal

# Each tuple: (test id, HTTP status that drives the failure category)
_SCENARIOS = [
    # run 1 — auth + backend outage
    [("checkout::test_login", 401), ("checkout::test_pay", 500), ("checkout::test_cart", 500)],
    # run 2 — backend recovered, one new timeout
    [("checkout::test_pay", 500), ("search::test_query", 504)],
    # run 3 — flaky login reappears, everything else green
    [("checkout::test_login", 401)],
    # run 4 — clean-ish run, single UI issue
    [("profile::test_avatar", 422)],
]


def _analyze(test_id: str, status: int):
    ctx = (
        FailureContextBuilder()
        .with_test(test_id, framework="playwright")
        .with_network([{"method": "GET", "url": "/api", "status": status}])
        .with_execution(environment="staging", browser="chromium")
        .build()
    )
    return FailureAnalyzer().analyze(ctx), ctx


def main() -> None:
    portal = QualityPortal("reports")
    total_tests = 6  # pretend the suite has 6 tests each run

    for scenario in _SCENARIOS:
        portal.begin_run(framework="playwright", environment="staging", browser="chromium")
        for test_id, status in scenario:
            result, ctx = _analyze(test_id, status)
            portal.add_failure(result, ctx)
        # record the passing tests so pass rate / quality score are realistic
        for i in range(total_tests - len(scenario)):
            portal.add_success(f"suite::passing_{i}")
        run = portal.finish_run()
        print(f"Recorded {run.run_id}: "
              f"{run.failed} failed / {run.total} total, "
              f"quality {run.quality_score} ({run.quality_band}), "
              f"health {run.build_health}, readiness {run.release_readiness}")

    print("\nPortal generated -> reports/index.html")


if __name__ == "__main__":
    main()
