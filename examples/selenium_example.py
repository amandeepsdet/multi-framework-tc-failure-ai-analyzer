"""Example: analyze a Selenium failure with the AIQA SDK.

The ``SeleniumAdapter`` reads ``current_url``, ``title``, ``page_source``, and
browser logs from a WebDriver and produces a generic ``FailureContext``.
"""

from __future__ import annotations

from aiqa import FailureAnalyzer, render
from aiqa.adapters import SeleniumAdapter


def on_test_failure(driver, exception: BaseException, test_name: str) -> None:
    context = SeleniumAdapter(driver=driver).collect_failure_context(
        exception,
        test_name=test_name,
        screenshot="screenshots/failure.png",
        browser="firefox",
        environment="qa",
    )
    print(render(FailureAnalyzer().analyze(context), "markdown", context))


if __name__ == "__main__":
    class FakeDriver:
        current_url = "https://app.example.com/orders"
        title = "Orders"
        page_source = "<html><body>Orders</body></html>"

        def get_log(self, _kind):
            return [{"level": "SEVERE", "message": "Uncaught TypeError: x is undefined"}]

    on_test_failure(
        FakeDriver(),
        Exception("no such element: Unable to locate element #checkout"),
        "orders::test_checkout",
    )
