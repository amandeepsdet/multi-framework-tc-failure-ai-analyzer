"""AI locator healing — framework-agnostic recovery from broken UI locators.

Public surface::

    from aiqa.healing import LocatorHealingEngine, heal_locator

    result = heal_locator("button.submit", dom_snapshot)
    if result.healed:
        print(result.best.playwright, result.best.reason)

Everything here is offline and dependency-free; it reasons over a DOM snapshot
using the standard library only and never imports a browser or framework.
"""

from __future__ import annotations

from .engine import LocatorHealingEngine, heal_locator
from .models import HealingResult, LocatorSuggestion
from .ranker import LocatorRanker

__all__ = [
    "LocatorHealingEngine",
    "heal_locator",
    "LocatorRanker",
    "HealingResult",
    "LocatorSuggestion",
]
