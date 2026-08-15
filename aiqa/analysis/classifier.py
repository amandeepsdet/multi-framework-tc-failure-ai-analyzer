"""Named failure-classification component.

A focused facade over the heuristic rule engine that returns a rich, structured
:class:`Classification` (category, subcategory, confidence, reason, owner, risk).
The :class:`~aiqa.analysis.analyzer.FailureAnalyzer` uses the same underlying
rules; this component exposes classification on its own for callers (and the
``classify`` CLI command) that only need the label, not a full analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.enums import FailureCategory, RiskLevel
from ..core.models import FailureContext
from .heuristics import HeuristicClassifier, risk_for
from .owners import OwnerResolver


@dataclass
class Classification:
    """Structured classification verdict."""

    category: FailureCategory = FailureCategory.UNKNOWN
    subcategory: str = ""
    confidence: int = 0
    reason: str = ""
    owner: str = ""
    risk_level: str = RiskLevel.MEDIUM.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "subcategory": self.subcategory,
            "confidence": self.confidence,
            "reason": self.reason,
            "owner": self.owner,
            "risk_level": self.risk_level,
        }


class FailureClassifier:
    """Classifies a :class:`FailureContext` into a :class:`Classification`."""

    def __init__(
        self,
        *,
        classifier: HeuristicClassifier | None = None,
        owner_resolver: OwnerResolver | None = None,
    ) -> None:
        self._classifier = classifier or HeuristicClassifier()
        self._owners = owner_resolver or OwnerResolver()

    def classify(self, context: FailureContext) -> Classification:
        verdict = self._classifier.classify(context)
        return Classification(
            category=verdict.category,
            subcategory=verdict.subcategory,
            confidence=verdict.confidence,
            reason=verdict.reason or verdict.summary,
            owner=self._owners.resolve(verdict.category),
            risk_level=risk_for(verdict.category).value,
        )
