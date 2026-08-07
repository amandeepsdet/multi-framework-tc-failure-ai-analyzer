"""The canonical AIQA SDK demo — the whole product in one runnable file.

It walks the complete pipeline end to end, entirely offline (no API keys, no
network, no browser, no application under test):

    FailureContext  ->  Analyzer  ->  Root Cause  ->  Suggested Fix
                    ->  Bug Report ->  HTML Report ->  Run History

Run it:
    python examples/sdk_demo.py

By default it writes the generated artifacts to ``sample_output/`` so you can
inspect a real Markdown / JSON / HTML report and bug report before installing.
Pass a different directory as the first argument to write elsewhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing the package first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import (
    BugReportBuilder,
    FailureAnalyzer,
    FailureContextBuilder,
    QualityPortal,
    render,
)


def build_context():
    """Step 1 — a FailureContext, exactly what any adapter produces."""
    return (
        FailureContextBuilder()
        .with_test("checkout::test_pay", suite="checkout", framework="pytest",
                   tags=["smoke", "payments"], execution_time_s=3.2)
        .with_exception_text(
            type="AssertionError",
            message="expected 200 but server returned HTTP 500",
            stacktrace="Traceback (most recent call last):\n  ...\nAssertionError: HTTP 500",
        )
        .with_assertion("expected 200 but server returned HTTP 500")
        .with_network([{"method": "POST", "url": "/api/pay", "status": 500}])
        .with_console([{"level": "error", "text": "Payment request failed"}])
        .with_execution(environment="staging", browser="chromium", url="/checkout")
        .build()
    )


def main(out_dir: str = "sample_output") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. FailureContext -----------------------------------------------------
    context = build_context()
    print(f"1. FailureContext built for: {context.metadata.test_name}")

    # 2. Analyzer -> 3. Root Cause -----------------------------------------
    result = FailureAnalyzer().analyze(context)
    print(f"2. Analyzed  -> category={result.category.value} "
          f"confidence={result.confidence.value}% owner={result.owner}")
    print(f"3. Root cause: {result.root_cause.summary}")

    # 4. Suggested Fix ------------------------------------------------------
    print("4. Suggested fix:")
    for rec in result.recommendations:
        print(f"     - {getattr(rec, 'action', rec)}")

    # 5. Bug Report ---------------------------------------------------------
    bug = BugReportBuilder().build(result, context)
    (out / "sample_bug_report.md").write_text(
        BugReportBuilder.to_markdown(bug), encoding="utf-8"
    )
    print(f"5. Bug report: {bug.title}")

    # 6. Reports (Markdown / JSON / HTML) ----------------------------------
    (out / "sample_report.md").write_text(render(result, "markdown", context), encoding="utf-8")
    (out / "sample_report.json").write_text(render(result, "json", context), encoding="utf-8")
    (out / "sample_report.html").write_text(render(result, "html", context), encoding="utf-8")
    print("6. Reports written: sample_report.{md,json,html}")

    # 7. Run History (Quality Portal dashboard) ----------------------------
    portal = QualityPortal(out / "reports")
    portal.begin_run(framework="pytest", environment="staging")
    portal.add_failure(result, context)
    portal.add_success("checkout::test_cart")
    portal.finish_run()
    print(f"7. Run history dashboard: {out / 'reports' / 'index.html'}")

    print(f"\nDone. Open the generated files under: {out.resolve()}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample_output")
