"""Deterministic, framework-agnostic heuristic classifier.

Given a :class:`FailureContext`, produce a ``(category, confidence, summary,
recommended_fix)`` verdict using explainable rules and the real evidence
(HTTP status codes, console errors, timeouts, empty DOM, assertions). It runs
with **zero dependencies and zero secrets**, so the SDK always produces an
analysis, and serves as the fallback when no LLM is configured.

This module contains no application or product terminology of any kind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.enums import FailureCategory, RiskLevel, Severity
from ..core.models import FailureContext

# Treat a 4xx/5xx number as an HTTP status only in an explicit HTTP context, so
# arbitrary 3-digit numbers (line numbers, addresses) are not misread as codes.
_HTTP_CONTEXT_RE = re.compile(r"(?:http|status|code|response|error)\D{0,10}([45]\d{2})\b", re.I)


@dataclass
class HeuristicVerdict:
    category: FailureCategory
    confidence: int
    summary: str
    recommended_fix: str
    subcategory: str = ""
    reason: str = ""


_SEVERITY_BY_CATEGORY: dict[FailureCategory, Severity] = {
    FailureCategory.BACKEND: Severity.CRITICAL,
    FailureCategory.API: Severity.CRITICAL,
    FailureCategory.AUTHENTICATION: Severity.CRITICAL,
    FailureCategory.AUTHORIZATION: Severity.MAJOR,
    FailureCategory.INFRASTRUCTURE: Severity.CRITICAL,
    FailureCategory.NETWORK: Severity.MAJOR,
    FailureCategory.PERFORMANCE: Severity.MAJOR,
    FailureCategory.LOCATOR: Severity.MAJOR,
    FailureCategory.UI: Severity.MAJOR,
    FailureCategory.DATA: Severity.MAJOR,
    FailureCategory.ASSERTION: Severity.MAJOR,
    FailureCategory.CONFIGURATION: Severity.MAJOR,
    FailureCategory.ENVIRONMENT: Severity.MAJOR,
    FailureCategory.BROWSER: Severity.MINOR,
    FailureCategory.FLAKY: Severity.MINOR,
    FailureCategory.UNKNOWN: Severity.MAJOR,
}


def severity_for(category: FailureCategory) -> Severity:
    return _SEVERITY_BY_CATEGORY.get(category, Severity.MAJOR)


_RISK_BY_CATEGORY: dict[FailureCategory, RiskLevel] = {
    FailureCategory.BACKEND: RiskLevel.CRITICAL,
    FailureCategory.API: RiskLevel.CRITICAL,
    FailureCategory.AUTHENTICATION: RiskLevel.CRITICAL,
    FailureCategory.SECURITY: RiskLevel.CRITICAL,
    FailureCategory.INFRASTRUCTURE: RiskLevel.CRITICAL,
    FailureCategory.DATABASE: RiskLevel.CRITICAL,
    FailureCategory.AUTHORIZATION: RiskLevel.HIGH,
    FailureCategory.NETWORK: RiskLevel.HIGH,
    FailureCategory.DEPENDENCY: RiskLevel.HIGH,
    FailureCategory.PERFORMANCE: RiskLevel.MEDIUM,
    FailureCategory.TIMEOUT: RiskLevel.MEDIUM,
    FailureCategory.LOCATOR: RiskLevel.MEDIUM,
    FailureCategory.ELEMENT_NOT_FOUND: RiskLevel.MEDIUM,
    FailureCategory.ELEMENT_NOT_VISIBLE: RiskLevel.MEDIUM,
    FailureCategory.UI: RiskLevel.MEDIUM,
    FailureCategory.FRONTEND: RiskLevel.MEDIUM,
    FailureCategory.ASSERTION: RiskLevel.MEDIUM,
    FailureCategory.DATA: RiskLevel.MEDIUM,
    FailureCategory.CONFIGURATION: RiskLevel.MEDIUM,
    FailureCategory.ENVIRONMENT: RiskLevel.MEDIUM,
    FailureCategory.BROWSER: RiskLevel.LOW,
    FailureCategory.MOBILE: RiskLevel.MEDIUM,
    FailureCategory.FLAKY: RiskLevel.LOW,
    FailureCategory.UNKNOWN: RiskLevel.MEDIUM,
}


def risk_for(category: FailureCategory) -> RiskLevel:
    return _RISK_BY_CATEGORY.get(category, RiskLevel.MEDIUM)


class HeuristicClassifier:
    """Explainable rule engine over a :class:`FailureContext`."""

    def classify(self, context: FailureContext) -> HeuristicVerdict:
        ev = context.evidence
        text = " ".join(
            [
                context.exception.type,
                context.exception.message,
                context.assertion_message,
                context.exception.stacktrace[-2000:],
            ]
        ).lower()

        statuses = [n.status for n in ev.network if isinstance(n.status, int)]
        server_errors = [s for s in statuses if s and 500 <= s < 600]
        auth_errors = [s for s in statuses if s in (401, 403)]
        text_codes = [int(c) for c in _HTTP_CONTEXT_RE.findall(text)]
        text_5xx = [c for c in text_codes if 500 <= c < 600]

        # 1. Backend — 5xx responses are strong signals.
        if server_errors or text_5xx:
            code = server_errors[0] if server_errors else text_5xx[0]
            return HeuristicVerdict(
                FailureCategory.BACKEND,
                92,
                f"A backend service returned HTTP {code}; the client could not obtain valid data.",
                "Inspect server logs for the failing endpoint; the defect is server-side, not in the test.",
                subcategory=f"HTTP {code} Server Error",
                reason=f"HTTP {code} returned from a backend endpoint before the client could proceed.",
            )
        # 2. Authentication / Authorization.
        if 401 in auth_errors or 401 in text_codes or "unauthor" in text or "unauthenticated" in text:
            return HeuristicVerdict(
                FailureCategory.AUTHENTICATION,
                88,
                "The request was rejected as unauthenticated (HTTP 401).",
                "Verify credentials/token validity and that authentication succeeded before the protected call.",
                subcategory="Invalid or expired credentials",
                reason="HTTP 401 Unauthorized returned before protected resource access.",
            )
        if 403 in auth_errors or 403 in text_codes or "forbidden" in text:
            return HeuristicVerdict(
                FailureCategory.AUTHORIZATION,
                86,
                "The authenticated principal lacks permission for the resource (HTTP 403).",
                "Check the account's roles/permissions for the target resource.",
                subcategory="Insufficient permissions",
                reason="HTTP 403 Forbidden returned for the requested resource.",
            )
        # 3. Locator / element issues.
        if any(k in text for k in (
            "locator", "selector", "waiting for", "element is not", "no node found",
            "no such element", "strict mode", "not visible", "not clickable",
        )):
            return HeuristicVerdict(
                FailureCategory.LOCATOR,
                80,
                "A locator did not resolve to an interactable element within the timeout.",
                "Compare the expected selector against the current DOM; the UI markup likely changed.",
                subcategory="Stale or changed selector",
                reason="Locator failed to resolve within the timeout; the UI markup likely changed.",
            )
        # 4. Timeout / network.
        if any(k in text for k in ("timeout", "timed out", "err_connection", "econnrefused", "unreachable")):
            is_conn = "connection" in text or "econnrefused" in text or "unreachable" in text
            category = FailureCategory.NETWORK if is_conn else FailureCategory.PERFORMANCE
            return HeuristicVerdict(
                category,
                72,
                "The operation exceeded its time budget or the host was unreachable.",
                "Check environment availability and latency; raise the timeout only if the app is genuinely slow.",
            )
        # 5. Empty / unrendered page.
        if ("did not render" in text or "blank" in text) or (ev.dom_snapshot and len(ev.dom_snapshot.strip()) < 200):
            return HeuristicVerdict(
                FailureCategory.UI,
                68,
                "The page rendered empty or without the expected content.",
                "Confirm the page loaded and data-bound content was received; inspect console errors.",
            )
        # 6. Assertion mismatch.
        if any(k in text for k in ("assert", "expected", "to equal", "to be", "did not match")):
            return HeuristicVerdict(
                FailureCategory.ASSERTION,
                66,
                "An assertion failed: the observed value did not match the expected value.",
                "Verify the expected value and the data the system produced under test.",
            )
        # 7. Data / range issues.
        if any(k in text for k in ("out of range", "outside", "not numeric", "invalid value", "type error")):
            return HeuristicVerdict(
                FailureCategory.DATA,
                64,
                "A value fell outside its expected range or type.",
                "Validate the input/output data and the configured bounds.",
            )
        # 8. Console errors present.
        if any(c.level == "error" for c in ev.console):
            first = next((c.text for c in ev.console if c.level == "error"), "")
            return HeuristicVerdict(
                FailureCategory.UI,
                60,
                "Client console errors were logged during the failing step.",
                f"Review the console error stack (e.g. {first[:120]}); a client-side exception likely blocked the flow.",
            )
        # 9. Unknown.
        return HeuristicVerdict(
            FailureCategory.UNKNOWN,
            40,
            "Insufficient distinctive signals to classify automatically.",
            "Review the stacktrace and screenshot; configure an LLM provider for deeper analysis.",
        )
