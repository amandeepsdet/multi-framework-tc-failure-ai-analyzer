"""Phase 1 intelligence demo — classification, healing, bug generation, reasoning.

Showcases the enterprise-grade AI capabilities on top of the base SDK, fully
offline (no API keys, no browser, no application under test):

    1. Intelligent Failure Classification  (category + subcategory + risk + owner)
    2. AI Confidence Reasoning             (why the AI reached its conclusion)
    3. AI Locator Healing                  (recover a broken UI locator)
    4. Intelligent Bug Generator           (professional, multi-tracker export)

Run it:
    python examples/phase1_intelligence_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing the package first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiqa import (
    BugExporter,
    BugGenerationEngine,
    FailureAnalyzer,
    FailureClassifier,
    FailureContextBuilder,
    heal_locator,
    render,
)


def _rule(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main(out_dir: str = "sample_output/phase1") -> None:
    # A realistic backend failure: HTTP 500 on a protected checkout call.
    context = (
        FailureContextBuilder()
        .with_test("tests/checkout/test_place_order.py::test_place_order")
        .with_exception_text(type="AssertionError", message="expected 200 but got 500")
        .with_assertion("Order confirmation was not displayed")
        .with_network([
            {"method": "POST", "url": "/api/checkout", "status": 500, "duration_ms": 812},
        ])
        .with_execution(environment="staging", browser="chromium", url="https://shop.example/checkout")
        .with_screenshot("screenshots/checkout_failure.png")
        .build()
    )

    # 1) Standalone classification -------------------------------------------- #
    _rule("1. Intelligent Failure Classification")
    classification = FailureClassifier().classify(context)
    print(f"Category    : {classification.category.value} / {classification.subcategory}")
    print(f"Confidence  : {classification.confidence}%")
    print(f"Risk        : {classification.risk_level}")
    print(f"Owner       : {classification.owner}")
    print(f"Reason      : {classification.reason}")

    # 2) Full analysis with confidence reasoning ------------------------------ #
    _rule("2. AI Confidence Reasoning")
    result = FailureAnalyzer().analyze(context)
    cr = result.reasoning_detail
    print(f"{cr.badge} — {cr.confidence}%")
    for point in cr.reasoning_points:
        print(f"  \u2713 {point}")
    for conflict in cr.conflicting_evidence:
        print(f"  \u26a0 {conflict}")
    print(f"\nAssessment  : {cr.assessment}")
    if cr.low_confidence_note:
        print(f"Note        : {cr.low_confidence_note}")

    # 3) Locator healing ------------------------------------------------------ #
    _rule("3. AI Locator Healing")
    dom = (
        "<html><body><form>"
        "<button class='btn primary' data-testid='place-order-btn' id='order'>Place order</button>"
        "</form></body></html>"
    )
    healing = heal_locator("button.place-order", dom, target_text="Place order")
    print(f"Old locator : {healing.old_locator}")
    print(f"Why broke   : {healing.failure_reason}")
    best = healing.best
    print(f"Suggested   : {best.playwright}  [{best.quality}, {best.confidence}%]")
    print(f"Reason      : {best.reason}")
    print("Alternatives:")
    for s in healing.suggestions[1:4]:
        print(f"  - {s.strategy:8} {s.quality:5} {s.css or s.xpath}")

    # 4) Intelligent bug generation + export ---------------------------------- #
    _rule("4. Intelligent Bug Generator")
    bug = BugGenerationEngine().build(result, context)
    print(f"Title       : {bug.title}")
    print(f"Severity    : {bug.severity}  Priority: {bug.priority}  Risk: {bug.risk}")
    print(f"Preventive  : {bug.preventive_action}")

    written = BugExporter().export_all(bug, out_dir)
    print(f"\nExported {len(written)} tracker files to {out_dir}/:")
    for name in written:
        print(f"  - {name}")

    # Also drop the analysis HTML report next to the bug files.
    report_path = Path(out_dir) / "analysis.html"
    report_path.write_text(render(result, "html", context), encoding="utf-8")
    print(f"  - {report_path.name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample_output/phase1")
