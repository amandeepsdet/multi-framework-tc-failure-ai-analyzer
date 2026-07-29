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
        if not result.recommendations:
            return head
        rec = result.recommendations[0].action
        return f"{head}\n       fix: {rec}"

    def summary_line(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        """Convenience one-liner (no newline), handy for logging on failure."""
        rc = result.root_cause
        name = context.test_name if context else "test"
        return (
            f"AI analysis: {rc.summary} ({rc.category.value}, "
            f"confidence={result.confidence.value}%) — owner={result.owner}"
        )
