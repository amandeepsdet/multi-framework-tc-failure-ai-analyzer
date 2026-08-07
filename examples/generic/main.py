"""Minimal generic (framework-agnostic) example.

Build a FailureContext from a plain dict, analyze it, and render a report.

Run:
    python examples/generic/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from aiqa import FailureAnalyzer, FailureContext, render


def main() -> None:
    # 1. FailureContext creation (works for Cypress, REST Assured, JUnit, CI, ...)
    context = FailureContext.from_dict(
        {
            "metadata": {"test_name": "orders::test_create", "framework": "generic"},
            "exception": {
                "type": "AssertionError",
                "message": "server returned HTTP 500",
            },
            "evidence": {
                "network": [{"method": "POST", "url": "/api/orders", "status": 500}]
            },
        }
    )

    # 2. Analysis
    result = FailureAnalyzer().analyze(context)

    # 3. Report generation
    print(render(result, "markdown", context))
    print(f"\ncategory={result.category.value} "
          f"confidence={result.confidence.value}% owner={result.owner}")


if __name__ == "__main__":
    main()
