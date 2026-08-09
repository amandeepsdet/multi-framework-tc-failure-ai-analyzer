"""Confidence-reasoning builder.

Turns a classified failure into a transparent, evidence-grounded explanation of
*why* the AI reached its confidence level. This makes the engine trustworthy
rather than a black box: every conclusion is backed by the concrete signals that
were actually present in the :class:`FailureContext`.

It is framework-agnostic and dependency-free — it inspects only the generic
evidence already collected by the adapters.
"""

from __future__ import annotations

from ..core.enums import FailureCategory
from ..core.models import ConfidenceReasoning, FailureContext, SimilarFailure

_MAX_POINTS = 8
_LOW_CONFIDENCE_THRESHOLD = 70

# Which evidence sources most strongly corroborate a given category. Used to
# flag *conflicting* signals when an expected corroborator is missing.
_EXPECTED_SOURCES: dict[FailureCategory, tuple[str, ...]] = {
    FailureCategory.BACKEND: ("Network", "API"),
    FailureCategory.API: ("Network", "API"),
    FailureCategory.AUTHENTICATION: ("Network",),
    FailureCategory.AUTHORIZATION: ("Network",),
    FailureCategory.NETWORK: ("Network",),
    FailureCategory.LOCATOR: ("DOM",),
    FailureCategory.ELEMENT_NOT_FOUND: ("DOM",),
    FailureCategory.ELEMENT_NOT_VISIBLE: ("DOM", "Screenshot"),
    FailureCategory.UI: ("Screenshot", "Console"),
    FailureCategory.FRONTEND: ("Console",),
}


class ConfidenceReasoningBuilder:
    """Builds a :class:`ConfidenceReasoning` from a context and a verdict."""

    def build(
        self,
        context: FailureContext,
        *,
        category: FailureCategory,
        confidence: int,
        similar: list[SimilarFailure] | None = None,
    ) -> ConfidenceReasoning:
        similar = similar or []
        points: list[str] = []
        supporting: list[str] = []
        conflicting: list[str] = []

        supporting.extend(self._category_signals(context, category, points))
        self._historical_signals(similar, points, supporting)
        available = set(context.evidence.available_sources())

        # Conflicting / missing-corroboration signals lower trust.
        expected = _EXPECTED_SOURCES.get(category, ())
        missing = [src for src in expected if src not in available]
        for src in missing:
            conflicting.append(f"Expected {src} evidence for a {category.value} failure was not captured")

        if category is FailureCategory.UNKNOWN:
            points.append("No decisive signal matched a known failure pattern")

        assessment = self._assessment(category, confidence)
        low_note = self._low_confidence_note(
            confidence, available, conflicting, category
        )

        return ConfidenceReasoning(
            confidence=confidence,
            reasoning_points=points[:_MAX_POINTS],
            supporting_evidence=supporting,
            conflicting_evidence=conflicting,
            assessment=assessment,
            low_confidence_note=low_note,
        )

    # -- signal extraction -------------------------------------------------- #
    def _category_signals(
        self, context: FailureContext, category: FailureCategory, points: list[str]
    ) -> list[str]:
        supporting: list[str] = []
        ev = context.evidence
        statuses = sorted({n.status for n in ev.network if n.status})

        server = [s for s in statuses if s and 500 <= s < 600]
        auth = [s for s in statuses if s in (401, 403)]

        if server:
            points.append(f"HTTP {server[0]} server error detected in network evidence")
            supporting.append("Network")
        if 401 in auth:
            points.append("HTTP 401 Unauthorized returned before protected resource access")
            supporting.append("Network")
        if 403 in auth:
            points.append("HTTP 403 Forbidden returned for the requested resource")
            supporting.append("Network")

        if context.exception.type:
            points.append(f"Exception raised: {context.exception.type}")
            supporting.append("Exception")
        if context.assertion_message:
            points.append(f"Assertion failed: {context.assertion_message[:80]}")
            supporting.append("Assertion")

        errors = [c for c in ev.console if c.level == "error"]
        if errors:
            points.append(f"{len(errors)} console error(s) logged during the failing step")
            supporting.append("Console")

        if category in (FailureCategory.LOCATOR, FailureCategory.ELEMENT_NOT_FOUND,
                        FailureCategory.ELEMENT_NOT_VISIBLE):
            if ev.dom_snapshot:
                points.append("DOM snapshot available for locator comparison")
                supporting.append("DOM")
        if category is FailureCategory.PERFORMANCE or category is FailureCategory.TIMEOUT:
            points.append("Operation exceeded its time budget (timeout signal)")

        # De-duplicate while preserving order.
        seen: set[str] = set()
        return [s for s in supporting if not (s in seen or seen.add(s))]

    @staticmethod
    def _historical_signals(
        similar: list[SimilarFailure], points: list[str], supporting: list[str]
    ) -> None:
        if not similar:
            return
        best = max(similar, key=lambda s: s.similarity)
        if best.similarity >= 50:
            points.append(
                f"Similar historical failure matched ({best.similarity}% similarity)"
            )
            supporting.append("Historical matches")

    @staticmethod
    def _assessment(category: FailureCategory, confidence: int) -> str:
        if category is FailureCategory.UNKNOWN:
            return (
                "Low confidence: the available evidence was insufficient to attribute "
                "the failure to a specific category."
            )
        level = "High" if confidence >= 85 else "Moderate" if confidence >= 60 else "Low"
        return (
            f"{level} confidence that this is a {category.value} failure, "
            "based on the corroborating evidence above."
        )

    @staticmethod
    def _low_confidence_note(
        confidence: int,
        available: set[str],
        conflicting: list[str],
        category: FailureCategory,
    ) -> str:
        if confidence >= _LOW_CONFIDENCE_THRESHOLD:
            return ""
        reasons: list[str] = []
        if len(available) <= 1:
            reasons.append("limited evidence was collected at failure time")
        if conflicting:
            reasons.append("some expected corroborating signals were missing")
        if category is FailureCategory.UNKNOWN:
            reasons.append("no signal matched a known failure pattern")
        if not reasons:
            reasons.append("the available signals were weak or ambiguous")
        return "Confidence is reduced because " + "; ".join(reasons) + "."
