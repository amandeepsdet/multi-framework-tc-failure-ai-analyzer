"""Generic demo: turn a failing test into an AI root cause and bug report.

This is the single, framework-agnostic demonstration of the AIQA SDK. It builds
a :class:`FailureContext` the way any adapter would, runs the offline AI
analyzer (no API keys, no network, no browser), and writes Markdown / JSON /
HTML reports plus a tracker-ready bug report — the same flow that runs
automatically when a real test fails in any framework.

Story:
    a test fails -> evidence is collected -> the AI analyzes the failure ->
    a root cause + fix are generated -> reports are saved.

Run it:
    pytest tests/test_ai_demo.py -v -o addopts=""
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiqa import FailureAnalyzer, FailureContext, render
from aiqa.reporting import BugReportBuilder

_REPORTS_DIR = Path(__file__).resolve().parent.parent / "ai_reports"


@pytest.fixture
def failing_test_context() -> FailureContext:
    """Evidence captured from a checkout test whose payment call returns 500.

    In real usage a framework adapter (Playwright, Selenium, pytest, Robot
    Framework, or the generic JSON adapter) produces this object. Here it is
    built by hand so the demo needs no application under test.
    """
    return FailureContext.from_dict(
        {
            "metadata": {"test_name": "checkout::test_pay", "framework": "pytest"},
            "exception": {
                "type": "AssertionError",
                "message": "expected 200 but server returned HTTP 500",
            },
            "evidence": {
                "network": [{"method": "POST", "url": "/api/pay", "status": 500}],
                "console": [{"type": "error", "text": "Payment request failed"}],
            },
        }
    )


@pytest.mark.demo
def test_ai_failure_analysis_end_to_end(failing_test_context: FailureContext) -> None:
    """Watch the SDK go from a failure to a root cause, fix, and bug report."""
    # 1. The offline AI engine analyzes the failure (deterministic, no keys).
    result = FailureAnalyzer().analyze(failing_test_context)

    # 2. Evidence-grounded root cause, confidence, category, and owning team.
    assert result.root_cause.summary
    assert 0 <= result.confidence.value <= 100
    assert result.category.value == "Backend"  # HTTP 500 -> Backend
    assert result.owner
    assert result.evidence  # every claim is grounded in a real signal

    # 3. A concrete, actionable fix recommendation is produced.
    assert result.recommendations

    # 4. The result renders in every reporting format and is saved to disk.
    _REPORTS_DIR.mkdir(exist_ok=True)
    (_REPORTS_DIR / "demo_analysis.md").write_text(
        render(result, "markdown", failing_test_context), encoding="utf-8"
    )
    (_REPORTS_DIR / "demo_analysis.json").write_text(
        render(result, "json", failing_test_context), encoding="utf-8"
    )
    (_REPORTS_DIR / "demo_analysis.html").write_text(
        render(result, "html", failing_test_context), encoding="utf-8"
    )
    assert json.loads((_REPORTS_DIR / "demo_analysis.json").read_text(encoding="utf-8"))

    # 5. A tracker-ready bug report is generated and saved as Markdown.
    bug = BugReportBuilder().build(result, failing_test_context)
    assert bug.title.startswith("[Backend]")
    (_REPORTS_DIR / "demo_bug_report.md").write_text(
        BugReportBuilder.to_markdown(bug), encoding="utf-8"
    )
