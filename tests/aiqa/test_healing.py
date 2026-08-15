"""Tests for AI locator healing (framework-agnostic recovery)."""

from __future__ import annotations

import json

import pytest

from aiqa.healing import LocatorHealingEngine, LocatorRanker, heal_locator
from aiqa.healing.models import LocatorSuggestion

pytestmark = pytest.mark.sdk

DOM = """
<html><body>
  <form id="login">
    <input name="email" id="email-field" type="email" />
    <button class="btn primary" data-testid="submit-btn" id="submit">Sign in</button>
  </form>
</body></html>
"""


def test_heals_stale_class_locator_to_stable_test_id():
    result = heal_locator("button.submit", DOM, target_text="Sign in")
    assert result.healed
    assert result.best.strategy == "test-id"
    assert result.best.quality == "Best"
    assert "submit-btn" in result.best.playwright
    assert result.failure_reason


def test_generates_all_framework_syntaxes():
    result = heal_locator("button.submit", DOM, target_text="Sign in")
    best = result.best
    assert best.playwright and best.selenium and best.css and best.xpath and best.robotframework


def test_ranking_orders_best_first():
    result = heal_locator("button.submit", DOM, target_text="Sign in")
    confidences = [s.confidence for s in result.suggestions]
    assert confidences == sorted(confidences, reverse=True)
    assert result.suggestions[0].quality == "Best"


def test_attribute_hint_resolves_target():
    result = heal_locator("#old-email", DOM, target_attributes={"name": "email"})
    assert result.healed
    assert any(s.strategy in ("id", "name") for s in result.suggestions)


def test_empty_dom_returns_reason_without_suggestions():
    result = heal_locator("button.submit", "")
    assert not result.healed
    assert result.suggestions == []
    assert "unavailable" in result.failure_reason.lower()


def test_corrupted_dom_does_not_raise():
    result = heal_locator(
        "button.submit", "<html><body><button data-testid='x'>Go", target_text="Go"
    )
    # Malformed markup must be tolerated (no exception).
    assert isinstance(result.suggestions, list)


def test_missing_element_reports_no_match_gracefully():
    result = heal_locator(
        "button.nonexistent",
        "<html><body><p>nothing interactive</p></body></html>",
        target_text="does-not-exist",
    )
    assert isinstance(result.healed, bool)
    assert result.failure_reason


def test_result_is_json_serialisable():
    result = heal_locator("button.submit", DOM, target_text="Sign in")
    payload = json.loads(result.to_json())
    assert payload["best"]["strategy"] == "test-id"


def test_ranker_labels_quality_tiers():
    ranker = LocatorRanker()
    ranked = ranker.rank(
        [
            LocatorSuggestion(strategy="css", confidence=55),
            LocatorSuggestion(strategy="test-id", confidence=95),
            LocatorSuggestion(strategy="text", confidence=70),
        ]
    )
    assert [s.quality for s in ranked] == ["Best", "Good", "Weak"]


def test_engine_is_reusable():
    engine = LocatorHealingEngine()
    r1 = engine.heal("button.submit", DOM, target_text="Sign in")
    r2 = engine.heal("#email-field", DOM, target_attributes={"name": "email"})
    assert r1.healed and r2.healed
