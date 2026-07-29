"""Example: analyze a Playwright failure with the AIQA SDK.

Run inside a Playwright test's failure handler (e.g. a pytest fixture or a
try/except around your steps). The SDK never touches Playwright itself — the
``PlaywrightAdapter`` does, and hands the engine a generic ``FailureContext``.
"""

from __future__ import annotations

from aiqa import FailureAnalyzer, render
from aiqa.adapters import PlaywrightAdapter, PlaywrightEventRecorder


def on_test_failure(page, exception: BaseException, test_name: str) -> None:
    # Attach a recorder at test start to capture console + network live:
    #   recorder = PlaywrightEventRecorder(page)
    recorder = getattr(page, "_aiqa_recorder", None)

    adapter = PlaywrightAdapter(page=page, recorder=recorder)
    context = adapter.collect_failure_context(
        exception,
        test_name=test_name,
        screenshot="screenshots/failure.png",
        browser="chromium",
        environment="staging",
    )

    result = FailureAnalyzer().analyze(context)
    print(render(result, "console", context))
    # Persist a full report if you like:
    # Path("report.md").write_text(render(result, "markdown", context))


if __name__ == "__main__":
    # Minimal runnable demo with a fake page (no browser needed).
    class FakePage:
        url = "https://app.example.com/login"

        def title(self):
            return "Login"

        def content(self):
            return "<html><body>Login</body></html>"

    on_test_failure(FakePage(), TimeoutError("locator button#submit not found"), "login::test_submit")
