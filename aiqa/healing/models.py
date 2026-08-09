"""Data models for AI locator healing.

Pure, framework-agnostic dataclasses describing a locator-healing suggestion and
the overall healing result. They carry *why* a locator failed and *why* each
replacement is proposed, never a random guess.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LocatorSuggestion:
    """A single proposed replacement locator, in multiple framework syntaxes."""

    strategy: str = ""          # e.g. "data-testid", "id", "role", "text", "css", "xpath"
    confidence: int = 0         # 0-100
    reason: str = ""
    quality: str = "Weak"       # "Best" | "Good" | "Weak" (set by the ranker)
    playwright: str = ""
    selenium: str = ""
    css: str = ""
    xpath: str = ""
    robotframework: str = ""

    def __post_init__(self) -> None:
        self.confidence = max(0, min(100, int(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealingResult:
    """The outcome of a healing attempt for one failed locator."""

    old_locator: str = ""
    failure_reason: str = ""
    suggestions: list[LocatorSuggestion] = field(default_factory=list)

    @property
    def best(self) -> LocatorSuggestion | None:
        return self.suggestions[0] if self.suggestions else None

    @property
    def healed(self) -> bool:
        return bool(self.suggestions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_locator": self.old_locator,
            "failure_reason": self.failure_reason,
            "healed": self.healed,
            "best": self.best.to_dict() if self.best else None,
            "suggestions": [s.to_dict() for s in self.suggestions],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
