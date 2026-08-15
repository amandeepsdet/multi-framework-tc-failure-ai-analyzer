"""Plain-text console reporter (single-line summary + optional detail)."""

from __future__ import annotations

from ..core.interfaces import Reporter
from ..core.models import AnalysisResult, FailureContext
from .base import register_reporter


@register_reporter
class ConsoleReporter(Reporter):
    format = "console"

    def render(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        rc = result.root_cause
        name = context.test_name if context else "test"
        head = (
            f"[AIQA] {name}: {rc.summary} "
            f"({rc.category.value}, confidence={result.confidence.value}%) "
            f"— owner={result.owner}"
        )
        lines = [head]
        cr = result.reasoning_detail
        if cr is not None:
            lines.append(f"       {cr.badge} confidence — {cr.assessment}")
            for p in cr.reasoning_points[:5]:
                lines.append(f"         ✓ {p}")
            if cr.low_confidence_note:
                lines.append(f"         ! {cr.low_confidence_note}")
        if result.recommendations:
            lines.append(f"       fix: {result.recommendations[0].action}")
        return "\n".join(lines)

    def summary_line(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        """Convenience one-liner (no newline), handy for logging on failure."""
        rc = result.root_cause
        return (
            f"AI analysis: {rc.summary} ({rc.category.value}, "
            f"confidence={result.confidence.value}%) — owner={result.owner}"
        )
