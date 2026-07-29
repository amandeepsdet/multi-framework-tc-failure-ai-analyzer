"""Offline unit tests for the AI engine core (analyzer, security, RAG, models)."""

from __future__ import annotations

import pytest

from qa_ai_engine.embeddings import HashEmbedder, cosine_similarity
from qa_ai_engine.failure_analyzer import FailureAnalyzer
from qa_ai_engine.models import Evidence, FailureCategory, FailureRecord
from qa_ai_engine.security import mask_text, scrub


@pytest.fixture
def analyzer() -> FailureAnalyzer:
    return FailureAnalyzer()


def _record(**evidence) -> FailureRecord:
    return FailureRecord(test_name="test_x", evidence=Evidence(**evidence))


@pytest.mark.ai
def test_backend_5xx_is_classified_as_backend(analyzer: FailureAnalyzer) -> None:
    record = _record(
        assertion_message="widget empty",
        network=[{"method": "GET", "url": "/api/telemetry", "status": 500}],
    )
    result = analyzer._analyze_heuristically(record)
    assert result.category is FailureCategory.BACKEND
    assert result.confidence >= 85
    assert any("500" in e for e in result.evidence)


@pytest.mark.ai
def test_401_is_authentication(analyzer: FailureAnalyzer) -> None:
    record = _record(network=[{"method": "GET", "url": "/api/tenant/devices", "status": 401}])
    result = analyzer._analyze_heuristically(record)
    assert result.category is FailureCategory.AUTHENTICATION


@pytest.mark.ai
def test_locator_failure_is_locator(analyzer: FailureAnalyzer) -> None:
    record = _record(
        exception_type="TimeoutError",
        exception_message="locator.wait_for: Timeout 30000ms exceeded waiting for selector",
    )
    result = analyzer._analyze_heuristically(record)
    assert result.category in (FailureCategory.LOCATOR, FailureCategory.PERFORMANCE)


@pytest.mark.ai
def test_unknown_when_no_signals(analyzer: FailureAnalyzer) -> None:
    result = analyzer._analyze_heuristically(_record())
    assert result.category is FailureCategory.UNKNOWN
    assert 0 <= result.confidence <= 100


@pytest.mark.ai
def test_category_coercion() -> None:
    assert FailureCategory.coerce("Backend") is FailureCategory.BACKEND
    assert FailureCategory.coerce("server 500 error") is FailureCategory.BACKEND
    assert FailureCategory.coerce(None) is FailureCategory.UNKNOWN


@pytest.mark.ai
def test_secret_masking_redacts_jwt_and_password() -> None:
    text = 'password: "hunter2" token=eyJhbGciOi.JzdWIiOiJ4.AAAABBBB Bearer eyJx.y.z'
    masked = mask_text(text)
    assert "hunter2" not in masked
    assert "eyJhbGciOi" not in masked
    assert "REDACTED" in masked


@pytest.mark.ai
def test_scrub_masks_sensitive_keys() -> None:
    data = {"username": "amy", "password": "s3cret", "nested": {"jwt_token": "abc"}}
    scrubbed = scrub(data, enabled=True)
    assert scrubbed["username"] == "amy"
    assert scrubbed["password"] == "***REDACTED***"
    assert scrubbed["nested"]["jwt_token"] == "***REDACTED***"


@pytest.mark.ai
def test_scrub_disabled_is_noop() -> None:
    data = {"password": "s3cret"}
    assert scrub(data, enabled=False) == data


@pytest.mark.ai
def test_hash_embedder_similarity() -> None:
    embedder = HashEmbedder(dim=128)
    a = embedder.embed("dashboard widget did not render HTTP 500")
    b = embedder.embed("widget empty because backend returned HTTP 500")
    c = embedder.embed("login form username password field visible")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


@pytest.mark.ai
def test_evidence_available_sources() -> None:
    ev = Evidence(dom="<html></html>", network=[{"status": 500}], screenshot="/tmp/x.png")
    sources = ev.available_sources()
    assert "DOM" in sources and "Network" in sources and "Screenshot" in sources


@pytest.mark.ai
def test_failure_record_roundtrip() -> None:
    record = _record(assertion_message="boom", exception_type="AssertionError")
    restored = FailureRecord.from_dict(record.to_dict())
    assert restored.test_name == record.test_name
    assert restored.evidence.assertion_message == "boom"
