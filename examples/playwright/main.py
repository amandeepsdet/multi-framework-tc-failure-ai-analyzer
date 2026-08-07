"""Minimal Playwright example.

Uses a tiny fake ``page`` so the file runs without a browser. In a real suite,
pass your live Playwright ``page`` and attach the recorder at test start.

Run:
    python examples/playwright/main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from aiqa import FailureAnalyzer, render
from aiqa.adapters import PlaywrightAdapter, PlaywrightEventRecorder


class _FakePage:
    """Stand-in for a Playwright Page (duck-typed)."""

    url = "https://app.example.com/login"

    def title(self) -> str:
        return "Login"

    def content(self) -> str:
        return "<html><body><form id='login'></form></body></html>"

    def on(self, *_args, **_kwargs) -> None:  # recorder subscribes to events
        pass


def main() -> None:
    page = _FakePage()
    recorder = PlaywrightEventRecorder(page)  # attach at test start

    try:
        raise TimeoutError(
            "locator.click: Timeout 30000ms exceeded waiting for "
            "get_by_role('button', name='Sign in')"
        )
    except TimeoutError as exc:
        # 1. FailureContext creation via the Playwright adapter
        context = PlaywrightAdapter(page=page, recorder=recorder).collect_failure_context(
            exc, test_name="login::test_submit", browser="chromium"
        )

    # 2. Analysis
    result = FailureAnalyzer().analyze(context)

    # 3. Report generation
    print(render(result, "markdown", context))


if __name__ == "__main__":
    main()
