"""Example: analyze a failure described by plain JSON (any framework).

Because the engine consumes a generic ``FailureContext``, ANY tool that can
emit JSON — Cypress, REST Assured, JUnit, NUnit, TestNG, a CI script — can use
the SDK. Point ``GenericAdapter`` at a dict, a JSON string, or a ``.json`` file.
"""

from __future__ import annotations

from aiqa import FailureAnalyzer, render
from aiqa.adapters import GenericAdapter

FAILURE_JSON = {
    "metadata": {
        "test_name": "orders.spec::creates order",
        "framework": "cypress",
        "tags": ["smoke", "orders"],
    },
    "exception": {
        "type": "CypressError",
        "message": "Timed out retrying: expected to find element #submit",
    },
    "evidence": {
        "console": [{"level": "error", "text": "GET /api/orders 503 (Service Unavailable)"}],
        "network": [{"method": "GET", "url": "/api/orders", "status": 503}],
        "screenshot": "cypress/screenshots/orders.png",
    },
    "execution": {"environment": "staging", "browser": "electron"},
    "assertion_message": "expected to find element #submit",
}


def main() -> None:
    context = GenericAdapter().collect_failure_context(FAILURE_JSON)
    result = FailureAnalyzer().analyze(context)
    print(render(result, "markdown", context))
    print("\n=== JSON ===")
    print(render(result, "json", context))


if __name__ == "__main__":
    main()
