"""Markdown reporter."""

from __future__ import annotations

from ..core.interfaces import Reporter
from ..core.models import AnalysisResult, FailureContext
from .base import register_reporter


@register_reporter
class MarkdownReporter(Reporter):
    format = "markdown"

    def render(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        rc = result.root_cause
        lines = [
            f"# AI Failure Analysis — {context.test_name if context else 'test'}",
            "",
            f"- **Category:** {rc.category.value}",
            f"- **Confidence:** {result.confidence.value}%",
            f"- **Severity:** {result.severity.value}",
            f"- **Owner:** {result.owner}",
            f"- **Source:** {result.source}",
            "",
            "## Root cause",
            rc.summary or "_n/a_",
        ]
        if rc.detail:
            lines += ["", rc.detail]
        if result.confidence.rationale:
            lines += ["", f"_Confidence rationale: {result.confidence.rationale}_"]

        if result.evidence:
            lines += ["", "## Evidence"]
            lines += [f"- {e}" for e in result.evidence]

        if result.recommendations:
            lines += ["", "## Recommendations"]
            for r in result.recommendations:
                text = f"- {r.action}"
                if r.rationale:
                    text += f" — {r.rationale}"
                lines.append(text)

        if result.similar_failures:
            lines += ["", "## Similar past failures"]
            for s in result.similar_failures:
                lines.append(f"- {s.test_name} ({s.category}, {s.similarity}% similar)")

        if result.reasoning:
            lines += ["", "## Reasoning", result.reasoning]

        return "\n".join(lines) + "\n"
