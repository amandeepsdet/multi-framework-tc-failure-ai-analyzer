"""AI locator-healing engine.

Attempts to recover from a UI locator failure without any framework dependency:
given the *old* locator and a DOM snapshot (plus optional hints), it diagnoses
*why* the locator broke and proposes ranked, explained replacements in every
supported framework syntax.

Pipeline::

    old locator + DOM  ->  diagnose reason  ->  resolve target element
                       ->  generate strategies  ->  rank  ->  HealingResult

It degrades gracefully: a missing/empty/corrupted DOM yields a result with a
clear ``failure_reason`` and no fabricated suggestions.
"""

from __future__ import annotations

import re

from .dom import Element, parse_dom
from .generators import generate_suggestions
from .models import HealingResult, LocatorSuggestion
from .ranker import LocatorRanker

_ID_RE = re.compile(r"#([\w-]+)|@id=['\"]([\w-]+)['\"]|\bid=([\w-]+)")
_CLASS_RE = re.compile(r"\.([\w-]+)|@class=['\"]([^'\"]+)['\"]")
_TESTID_RE = re.compile(r"data-test[\w-]*=['\"]?([\w -]+)['\"]?|get_by_test_id\(['\"]([^'\"]+)['\"]\)")
_TEXT_RE = re.compile(r"get_by_text\(['\"]([^'\"]+)['\"]\)|text\(\)=['\"]([^'\"]+)['\"]|normalize-space\(\)=['\"]([^'\"]+)['\"]")
_TAG_RE = re.compile(r"^\s*(?://)?([a-zA-Z][\w-]*)")


class LocatorHealingEngine:
    """Diagnoses and heals a broken locator against a DOM snapshot."""

    def __init__(self, *, ranker: LocatorRanker | None = None) -> None:
        self._ranker = ranker or LocatorRanker()

    def heal(
        self,
        old_locator: str,
        dom: str,
        *,
        target_text: str | None = None,
        target_attributes: dict[str, str] | None = None,
    ) -> HealingResult:
        elements = parse_dom(dom)
        if not elements:
            return HealingResult(
                old_locator=old_locator,
                failure_reason="DOM snapshot unavailable; cannot analyse the current markup.",
            )

        hints = self._extract_hints(old_locator)
        target = self._resolve_target(elements, hints, target_text, target_attributes)
        reason = self._diagnose(elements, hints, target)

        if target is None:
            return HealingResult(old_locator=old_locator, failure_reason=reason)

        suggestions = self._ranker.rank(generate_suggestions(target))
        return HealingResult(
            old_locator=old_locator,
            failure_reason=reason,
            suggestions=suggestions,
        )

    # -- hint extraction ---------------------------------------------------- #
    @staticmethod
    def _extract_hints(locator: str) -> dict[str, object]:
        loc = locator or ""
        ids = [g for m in _ID_RE.findall(loc) for g in m if g]
        classes: list[str] = []
        for m in _CLASS_RE.findall(loc):
            for g in m:
                classes.extend(g.split())
        test_ids = [g for m in _TESTID_RE.findall(loc) for g in m if g]
        texts = [g for m in _TEXT_RE.findall(loc) for g in m if g]
        tag_match = _TAG_RE.match(loc)
        tag = tag_match.group(1).lower() if tag_match else ""
        # Guard against matching CSS/XPath axis keywords as a tag.
        if tag in {"div", "span"} and (ids or classes):
            pass
        return {
            "ids": ids,
            "classes": classes,
            "test_ids": test_ids,
            "texts": texts,
            "tag": tag if tag not in {"page", "driver", "css", "xpath", "id", "name"} else "",
        }

    # -- target resolution -------------------------------------------------- #
    def _resolve_target(
        self,
        elements: list[Element],
        hints: dict[str, object],
        target_text: str | None,
        target_attributes: dict[str, str] | None,
    ) -> Element | None:
        # 1. Explicit attribute hints from the caller win.
        if target_attributes:
            for el in elements:
                if all(el.attr(k) == v for k, v in target_attributes.items()):
                    return el

        # 2. Explicit target text (or text parsed from the old locator).
        wanted_texts = [t for t in ([target_text] if target_text else []) if t]
        wanted_texts += list(hints.get("texts") or [])  # type: ignore[arg-type]
        for want in wanted_texts:
            match = self._best_text_match(elements, want)
            if match is not None:
                return match

        # 3. Same tag as the old locator, scored by shared classes.
        tag = str(hints.get("tag") or "")
        old_classes = set(hints.get("classes") or [])  # type: ignore[arg-type]
        candidates = [e for e in elements if not tag or e.tag == tag]
        candidates = [e for e in candidates if e.is_interactive()] or candidates
        if candidates:
            def score(e: Element) -> tuple[int, int]:
                shared = len(old_classes & set(e.classes()))
                stable = 1 if (e.test_id() or e.attr("id")) else 0
                return (shared, stable)
            best = max(candidates, key=score)
            return best
        return None

    @staticmethod
    def _best_text_match(elements: list[Element], want: str) -> Element | None:
        want_l = want.strip().lower()
        exact = [e for e in elements if e.text.strip().lower() == want_l]
        if exact:
            return min(exact, key=lambda e: len(e.text))
        partial = [e for e in elements if want_l and want_l in e.text.strip().lower()]
        if partial:
            return min(partial, key=lambda e: len(e.text))
        return None

    # -- diagnosis ---------------------------------------------------------- #
    @staticmethod
    def _diagnose(
        elements: list[Element], hints: dict[str, object], target: Element | None
    ) -> str:
        ids = list(hints.get("ids") or [])          # type: ignore[arg-type]
        classes = list(hints.get("classes") or [])  # type: ignore[arg-type]
        test_ids = list(hints.get("test_ids") or [])  # type: ignore[arg-type]

        present_ids = {e.attr("id") for e in elements if e.attr("id")}
        present_classes = {c for e in elements for c in e.classes()}
        present_test_ids = {v for e in elements if e.test_id() for v in (e.test_id() or ("", ""))}

        if test_ids and not any(t in present_test_ids for t in test_ids):
            return "The test id referenced by the old locator is no longer present in the DOM."
        if ids and not any(i in present_ids for i in ids):
            return "The element id changed or was removed; the old locator can no longer match it."
        if classes and not any(c in present_classes for c in classes):
            return "The CSS class used by the old locator changed; styling markup was refactored."
        if target is not None:
            return "The element still exists but under a different, more stable locator."
        return "The old locator no longer matches any element in the current DOM."


def heal_locator(
    old_locator: str,
    dom: str,
    *,
    target_text: str | None = None,
    target_attributes: dict[str, str] | None = None,
) -> HealingResult:
    """Convenience wrapper around :class:`LocatorHealingEngine`."""
    return LocatorHealingEngine().heal(
        old_locator, dom, target_text=target_text, target_attributes=target_attributes
    )
