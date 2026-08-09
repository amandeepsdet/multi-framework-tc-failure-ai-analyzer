"""Intelligent bug-report generation engine.

Upgrades the basic :class:`~aiqa.reporting.bug_report.BugReportBuilder` output
into a professional, evidence-linked bug report: natural-language title and
explanation, full environment, linked evidence (screenshots, logs, network,
stacktrace), suggested fix, preventive action, risk and confidence.

Framework- and application-agnostic: it derives everything from the generic
:class:`AnalysisResult` and optional :class:`FailureContext`.
"""

from __future__ import annotations

import platform

from ...core.enums import FailureCategory, Severity
from ...core.models import AnalysisResult, BugReport, FailureContext
from .titles import bug_title

_PRIORITY_BY_SEVERITY: dict[Severity, str] = {
    Severity.BLOCKER: "P0",
    Severity.CRITICAL: "P1",
    Severity.MAJOR: "P2",
    Severity.MINOR: "P3",
    Severity.TRIVIAL: "P4",
}

_PREVENTIVE_BY_CATEGORY: dict[FailureCategory, str] = {
    FailureCategory.AUTHENTICATION: "Add a pre-flight token-validity check and alert on auth expiry before protected calls.",
    FailureCategory.AUTHORIZATION: "Assert the test account's roles in setup and fail fast on permission drift.",
    FailureCategory.BACKEND: "Add backend health checks and contract tests for the failing endpoint in CI.",
    FailureCategory.API: "Add schema/contract validation for the API response in the pipeline.",
    FailureCategory.LOCATOR: "Adopt stable test ids (data-testid) and enable locator healing to survive DOM changes.",
    FailureCategory.ELEMENT_NOT_FOUND: "Adopt stable test ids and wait for the element's state explicitly.",
    FailureCategory.ELEMENT_NOT_VISIBLE: "Wait for visibility/enabled state before interaction instead of fixed sleeps.",
    FailureCategory.TIMEOUT: "Right-size timeouts and add readiness signals rather than blind waits.",
    FailureCategory.PERFORMANCE: "Add performance budgets and monitor the slow path in CI.",
    FailureCategory.NETWORK: "Add environment connectivity checks and retries with backoff for transient faults.",
    FailureCategory.FLAKY: "Quarantine and stabilise: remove timing races and shared-state coupling.",
    FailureCategory.ASSERTION: "Review the expected value's source of truth and pin test data.",
}


class BugGenerationEngine:
    """Builds an enriched, tracker-ready :class:`BugReport`."""

    def build(self, result: AnalysisResult, context: FailureContext | None = None) -> BugReport:
        rc = result.root_cause
        title = bug_title(result, context)
        summary = self._summary(result, context)
        environment = self._environment(context)
        exe = context.execution if context else None
        meta = context.metadata if context else None

        return BugReport(
            title=title,
            summary=summary,
            description=self._description(result, context),
            environment=environment,
            steps=self._steps(context),
            expected="The test completes successfully with the expected result.",
            actual=self._actual(result, context),
            evidence=list(result.evidence),
            severity=result.severity.value,
            priority=_PRIORITY_BY_SEVERITY.get(result.severity, "P2"),
            owner=result.owner,
            category=rc.category.value,
            subcategory=rc.subcategory,
            root_cause=rc.summary,
            suggested_fix=result.recommendations[0].action if result.recommendations else rc.detail,
            preventive_action=self._preventive(result),
            risk=result.risk_level,
            confidence=result.confidence.value,
            ai_explanation=self._ai_explanation(result),
            framework=meta.framework if meta else "",
            browser=exe.browser if exe else "",
            os=exe.os if exe else "",
            python_version=self._python_version(context),
            build=(exe.configuration.get("build", "") if exe else ""),
            commit=meta.git_commit if meta else "",
            stacktrace=context.exception.stacktrace if context else "",
            logs=self._logs(context),
            network=self._network(context),
            screenshots=self._screenshots(context),
        )

    # -- section builders --------------------------------------------------- #
    @staticmethod
    def _summary(result: AnalysisResult, context: FailureContext | None) -> str:
        rc = result.root_cause
        who = context.test_name if context else "an automated test"
        return f"While running {who}, {rc.summary[0].lower() + rc.summary[1:] if rc.summary else 'the test failed.'}"

    @staticmethod
    def _description(result: AnalysisResult, context: FailureContext | None) -> str:
        rc = result.root_cause
        parts = [rc.summary]
        if rc.reason:
            parts.append(rc.reason)
        if rc.detail:
            parts.append(rc.detail)
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _actual(result: AnalysisResult, context: FailureContext | None) -> str:
        if context and (context.assertion_message or context.exception.message):
            return context.assertion_message or context.exception.message
        return result.root_cause.summary

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

    @staticmethod
    def _preventive(result: AnalysisResult) -> str:
        return _PREVENTIVE_BY_CATEGORY.get(
            result.category,
            "Add targeted monitoring/assertions for this failure mode to catch regressions earlier.",
        )

    @staticmethod
    def _ai_explanation(result: AnalysisResult) -> str:
        cr = result.reasoning_detail
        if cr is None:
            return result.reasoning or ""
        bullets = "; ".join(cr.reasoning_points[:4])
        note = f" {cr.low_confidence_note}" if cr.low_confidence_note else ""
        return (f"{cr.assessment} Key signals: {bullets}." + note).strip()

    @staticmethod
    def _python_version(context: FailureContext | None) -> str:
        if context and context.execution.configuration.get("python_version"):
            return str(context.execution.configuration["python_version"])
        return platform.python_version()

    @staticmethod
    def _logs(context: FailureContext | None) -> list[str]:
        if context is None:
            return []
        return [f"{l.level.upper()}: {l.message}" for l in context.evidence.logs][:20]

    @staticmethod
    def _network(context: FailureContext | None) -> list[str]:
        if context is None:
            return []
        out = []
        for n in context.evidence.network[:20]:
            code = f" -> {n.status}" if n.status else ""
            out.append(f"{n.method or 'GET'} {n.url}{code}".strip())
        return out

    @staticmethod
    def _screenshots(context: FailureContext | None) -> list[str]:
        if context is None:
            return []
        shots = []
        if context.evidence.screenshot:
            shots.append(context.evidence.screenshot)
        shots.extend(
            path for name, path in context.evidence.artifacts.items()
            if "screenshot" in name.lower() or path.lower().endswith((".png", ".jpg", ".jpeg"))
        )
        return shots
