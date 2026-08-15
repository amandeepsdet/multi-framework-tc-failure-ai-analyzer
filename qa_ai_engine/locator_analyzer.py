"""Locator failure analysis.

When a Playwright locator fails to resolve, compare the expected selector
against the current DOM and propose the most likely replacements with a
similarity score. Works offline using ``difflib`` over candidate selectors
extracted from the DOM; upgrades to an LLM when configured.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from ._logging import get_logger
from .ai_config import AIConfig, ai_config
from .llm_client import BaseLLMClient, get_llm_client
from .prompt_builder import PromptBuilder

logger = get_logger("ai.locator_analyzer")

_ID_RE = re.compile(r'id="([^"]+)"')
_CLASS_RE = re.compile(r'class="([^"]+)"')
_NAME_RE = re.compile(r'formcontrolname="([^"]+)"')
_DATA_RE = re.compile(r'(data-[a-z-]+)="([^"]+)"')
_TESTID_RE = re.compile(r'(?:data-testid|data-test)="([^"]+)"')


@dataclass
class LocatorSuggestion:
    locator: str
    similarity: int
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"locator": self.locator, "similarity": self.similarity, "rationale": self.rationale}


@dataclass
class LocatorAnalysis:
    expected: str
    suggestions: list[LocatorSuggestion] = field(default_factory=list)
    source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected,
            "source": self.source,
            "suggestions": [s.to_dict() for s in self.suggestions],
        }


class LocatorAnalyzer:
    """Suggests replacement locators from a DOM snapshot."""

    def __init__(
        self,
        cfg: AIConfig = ai_config,
        llm: BaseLLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm or get_llm_client(cfg)
        self.prompts = prompt_builder or PromptBuilder(cfg)

    def analyze(self, expected_locator: str, dom: str, top_k: int = 5) -> LocatorAnalysis:
        if self.cfg.uses_llm and self.llm.is_available():
            try:
                return self._analyze_with_llm(expected_locator, dom, top_k)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM locator analysis failed (%s); using heuristic", exc)
        return self._analyze_heuristically(expected_locator, dom, top_k)

    def _candidates(self, dom: str) -> list[str]:
        selectors: set[str] = set()
        for tid in _TESTID_RE.findall(dom):
            selectors.add(f'[data-testid="{tid}"]')
        for name in _NAME_RE.findall(dom):
            selectors.add(f"[formcontrolname='{name}']")
        for _id in _ID_RE.findall(dom):
            selectors.add(f"#{_id}")
        for classes in _CLASS_RE.findall(dom):
            for cls in classes.split():
                if cls and not cls.startswith("ng-"):
                    selectors.add(f".{cls}")
        for attr, value in _DATA_RE.findall(dom):
            selectors.add(f'[{attr}="{value}"]')
        return list(selectors)

    def _analyze_heuristically(self, expected: str, dom: str, top_k: int) -> LocatorAnalysis:
        candidates = self._candidates(dom)
        scored = [
            LocatorSuggestion(
                locator=cand,
                similarity=round(difflib.SequenceMatcher(None, expected, cand).ratio() * 100),
                rationale="Selector present in current DOM with high textual similarity to the expected locator.",
            )
            for cand in candidates
        ]
        scored.sort(key=lambda s: s.similarity, reverse=True)
        return LocatorAnalysis(expected=expected, suggestions=scored[:top_k], source="heuristic")

    def _analyze_with_llm(self, expected: str, dom: str, top_k: int) -> LocatorAnalysis:
        prompt = self.prompts.build(
            "locator_analysis",
            {"expected_locator": expected, "dom": dom[: self.cfg.dom_max_chars]},
        )
        data = self.llm.complete_json(prompt)
        suggestions = [
            LocatorSuggestion(
                locator=item.get("locator", ""),
                similarity=int(item.get("similarity", 0) or 0),
                rationale=item.get("rationale", ""),
            )
            for item in data.get("suggestions", [])[:top_k]
        ]
        return LocatorAnalysis(expected=expected, suggestions=suggestions, source=self.llm.name)
