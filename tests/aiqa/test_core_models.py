"""Core domain model tests: serialization round-trips and invariants."""

from __future__ import annotations

import pytest

from aiqa import (
    AnalysisResult,
    ConfidenceScore,
    FailureCategory,
    FailureContext,
    FailureContextBuilder,
    RootCause,
    Severity,
)

pytestmark = pytest.mark.sdk


def test_failure_context_json_round_trip():
    ctx = (
        FailureContextBuilder()
        .with_test("suite::test_x", framework="playwright", tags=["smoke"])
        .with_exception(TimeoutError("boom"))
        .with_assertion("expected visible element")
        .with_network([{"method": "GET", "url": "/api", "status": 500}])
        .with_console([{"level": "error", "text": "kaboom"}])
        .with_execution(browser="chromium", environment="staging", url="http://x")
        .build()
    )
    restored = FailureContext.from_dict(ctx.to_dict())
    assert restored.test_name == "suite::test_x"
    assert restored.metadata.framework == "playwright"
    assert restored.evidence.network[0].status == 500
    assert restored.evidence.console[0].level == "error"
    assert restored.execution.browser == "chromium"


def test_confidence_is_clamped():
    assert ConfidenceScore(value=150).value == 100
    assert ConfidenceScore(value=-5).value == 0


def test_category_and_severity_coercion():
    assert FailureCategory.coerce("locator") is FailureCategory.LOCATOR
    assert FailureCategory.coerce("HTTP 500 server error") is FailureCategory.BACKEND
    assert FailureCategory.coerce(None) is FailureCategory.UNKNOWN
    assert Severity.coerce("critical") is Severity.CRITICAL
    assert Severity.coerce("nonsense") is Severity.MAJOR


def test_analysis_result_round_trip():
    result = AnalysisResult(
        root_cause=RootCause(summary="s", category=FailureCategory.API, detail="d"),
        confidence=ConfidenceScore(value=80, rationale="r"),
        severity=Severity.CRITICAL,
        owner="team",
    )
    restored = AnalysisResult.from_dict(result.to_dict())
    assert restored.category is FailureCategory.API
    assert restored.confidence.value == 80
    assert restored.severity is Severity.CRITICAL
    assert restored.owner == "team"


def test_searchable_text_includes_status_codes():
    ctx = FailureContextBuilder().with_test("t").with_network([{"status": 401}]).build()
    assert "401" in ctx.searchable_text()
