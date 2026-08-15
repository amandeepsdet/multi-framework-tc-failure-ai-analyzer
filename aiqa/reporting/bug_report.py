"""Bug report generation from an :class:`AnalysisResult`.

The builder is framework- and application-agnostic: it derives a tracker-ready
bug report purely from the analysis (and optional context metadata for the
environment/repro section). It makes no assumptions about any product feature.
"""

from __future__ import annotations

from ..core.enums import Severity
from ..core.models import AnalysisResult, BugReport, FailureContext

_PRIORITY_BY_SEVERITY: dict[Severity, str] = {
    Severity.BLOCKER: "P0",
    Severity.CRITICAL: "P1",
    Severity.MAJOR: "P2",
    Severity.MINOR: "P3",
    Severity.TRIVIAL: "P4",
}


class BugReportBuilder:
    """Builds a :class:`BugReport` from an analysis (+ optional context)."""

    def build(self, result: AnalysisResult, context: FailureContext | None = None) -> BugReport:
        rc = result.root_cause
        test_name = context.test_name if context else "automated test"
        environment = self._environment(context)
        steps = self._steps(context)
        expected = "The test completes successfully."
        actual = (
            (context.assertion_message or context.exception.message) if context else rc.summary
        ) or rc.summary
        fix = result.recommendations[0].action if result.recommendations else rc.detail

        return BugReport(
            title=f"[{rc.category.value}] {test_name}: {rc.summary[:100]}",
            description=rc.summary + (f"\n\n{rc.detail}" if rc.detail else ""),
            environment=environment,
            steps=steps,
            expected=expected,
            actual=actual,
            evidence=list(result.evidence),
            severity=result.severity.value,
            priority=_PRIORITY_BY_SEVERITY.get(result.severity, "P2"),
            owner=result.owner,
            root_cause=rc.summary,
            suggested_fix=fix,
        )

    @staticmethod
    def _environment(context: FailureContext | None) -> str:
        if context is None:
            return ""
        exe = context.execution
        parts = [p for p in (exe.environment, exe.browser, exe.os) if p]
        if context.metadata.framework:
            parts.append(context.metadata.framework)
        return " | ".join(parts)

    @staticmethod
    def _steps(context: FailureContext | None) -> list[str]:
        if context is None:
            return ["Run the failing test.", "Observe the failure."]
        steps = [f"Run test '{context.test_name}'."]
        if context.execution.url:
            steps.append(f"Navigate to {context.execution.url}.")
        steps.append("Observe the reported failure and attached evidence.")
        return steps

    # -- renderers ---------------------------------------------------------- #
    @staticmethod
    def to_markdown(bug: BugReport) -> str:
        lines = [
            f"# {bug.title}",
            "",
            f"- **Severity:** {bug.severity}  |  **Priority:** {bug.priority}  |  **Owner:** {bug.owner}",
            f"- **Environment:** {bug.environment or 'n/a'}",
            "",
            "## Description",
            bug.description or "_n/a_",
            "",
            "## Steps to reproduce",
        ]
        lines += [f"{i}. {s}" for i, s in enumerate(bug.steps, 1)]
        lines += [
            "",
            f"**Expected:** {bug.expected}",
            f"**Actual:** {bug.actual}",
        ]
        if bug.evidence:
            lines += ["", "## Evidence"] + [f"- {e}" for e in bug.evidence]
        if bug.suggested_fix:
            lines += ["", "## Suggested fix", bug.suggested_fix]
        return "\n".join(lines) + "\n"
