"""Rank locator suggestions from best to weakest.

Enforces the rule "never suggest random locators": every suggestion keeps its
explanation, and the ranker only orders and labels them by resilience so callers
can pick the most maintainable option first.
"""

from __future__ import annotations

from .models import LocatorSuggestion

_BEST_THRESHOLD = 85
_GOOD_THRESHOLD = 65

# Preference used to break ties between equally-confident strategies.
_STRATEGY_ORDER = {"test-id": 0, "id": 1, "role": 2, "name": 3, "text": 4, "css": 5, "xpath": 6}


class LocatorRanker:
    """Orders locator suggestions and labels their quality tier."""

    def rank(self, suggestions: list[LocatorSuggestion]) -> list[LocatorSuggestion]:
        ordered = sorted(
            suggestions,
            key=lambda s: (-s.confidence, _STRATEGY_ORDER.get(s.strategy, 9)),
        )
        for s in ordered:
            s.quality = self._quality(s.confidence)
        return ordered

    @staticmethod
    def _quality(confidence: int) -> str:
        if confidence >= _BEST_THRESHOLD:
            return "Best"
        if confidence >= _GOOD_THRESHOLD:
            return "Good"
        return "Weak"
