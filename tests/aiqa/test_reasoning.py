"""Tests for AI confidence reasoning (transparency of every conclusion)."""

from __future__ import annotations

import json

import pytest

from aiqa import FailureAnalyzer, FailureContextBuilder, get_reporter, render
from aiqa.core import ConfidenceReasoning

pytestmark = pytest.mark.sdk


def _ctx(**kw):
    b = FailureContextBuilder().with_test(kw.get("name", "t"))
    if kw.get("message") or kw.get("exc_type"):
        b.with_exception_text(type=kw.get("exc_type", "Error"), message=kw.get("message", ""))
    if kw.get("assertion"):
        b.with_assertion(kw["assertion"])
    if kw.get("network"):
        b.with_network(kw["network"])
    if kw.get("console"):
        b.with_console(kw["console"])
    if kw.get("dom"):
        b.with_dom(kw["dom"])
    return b.build()


def test_reasoning_attached_to_every_result():
    result = FailureAnalyzer().analyze(_ctx(network=[{"status": 500, "url": "/x"}]))
    cr = result.reasoning_detail
    assert cr is not None
    assert cr.reasoning_points  # at least one explained signal
    assert cr.assessment
    assert cr.confidence == result.confidence.value


def test_badge_levels():
    assert ConfidenceReasoning(confidence=90).level == "High"
    assert ConfidenceReasoning(confidence=90).badge.startswith("🟢")
    assert ConfidenceReasoning(confidence=70).level == "Medium"
    assert ConfidenceReasoning(confidence=70).badge.startswith("🟡")
    assert ConfidenceReasoning(confidence=40).level == "Low"
    assert ConfidenceReasoning(confidence=40).badge.startswith("🔴")


def test_low_confidence_is_explained():
    # Unknown failure -> low confidence -> must justify why.
    result = FailureAnalyzer().analyze(_ctx(message="something odd happened"))
    cr = result.reasoning_detail
    assert cr is not None
    assert cr.confidence < 70
    assert cr.low_confidence_note  # explains the low confidence


def test_conflicting_evidence_flagged_when_corroboration_missing():
    # A backend verdict from text only (no network capture) should flag the gap.
    result = FailureAnalyzer().analyze(_ctx(message="HTTP 500 server error"))
    cr = result.reasoning_detail
    assert cr is not None
    assert any("Network" in c for c in cr.conflicting_evidence)


def test_reasoning_serialised_in_json_and_markdown_and_html():
    result = FailureAnalyzer().analyze(_ctx(network=[{"status": 401, "url": "/login"}]))

    data = json.loads(render(result, "json"))
    rd = data["analysis"]["reasoning_detail"]
    assert rd["badge"] and rd["reasoning_points"]

    md = render(result, "markdown")
    assert "AI Confidence Reasoning" in md

    html = render(result, "html")
    assert "AI Confidence Reasoning" in html and "conf" in html

    console = get_reporter("console").render(result)
    assert "confidence" in console.lower()
