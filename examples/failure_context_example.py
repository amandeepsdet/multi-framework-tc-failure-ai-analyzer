"""Example: build a FailureContext by hand with the fluent builder.

When no adapter fits your tool, assemble a ``FailureContext`` directly. The
builder is the same one every adapter uses internally, so the resulting object
is identical to what an adapter would produce.

Run:
    python examples/failure_context_example.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import FailureAnalyzer, FailureContextBuilder, render


def main() -> None:
    context = (
        FailureContextBuilder()
        .with_test(
            "payments::test_refund",
            suite="payments",
            framework="custom",
            tags=["regression"],
            execution_time_s=1.8,
        )
        .with_exception_text(
            type="AssertionError",
            message="expected refund to succeed but API returned HTTP 403",
        )
        .with_assertion("expected refund to succeed but API returned HTTP 403")
        .with_network([{"method": "POST", "url": "/api/refund", "status": 403}])
        .with_logs(["Refund denied: caller lacks 'payments:write' scope"])
        .with_execution(environment="staging", url="/checkout/refund")
        .build()
    )

    result = FailureAnalyzer().analyze(context)
    print(render(result, "markdown", context))
    print(f"\ncategory={result.category.value} owner={result.owner}")


if __name__ == "__main__":
    main()
