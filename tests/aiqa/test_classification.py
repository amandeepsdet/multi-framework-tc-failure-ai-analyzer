"""Tests for the named FailureClassifier and OwnerResolver components."""

from __future__ import annotations

import pytest

from aiqa import Classification, FailureCategory, FailureClassifier, OwnerResolver
from aiqa import FailureContextBuilder, RiskLevel

pytestmark = pytest.mark.sdk


def _ctx(**kw):
    b = FailureContextBuilder().with_test("t")
    b.with_exception_text(type="Error", message=kw.get("message", ""))
    if kw.get("network"):
        b.with_network(kw["network"])
    if kw.get("assertion"):
        b.with_assertion(kw["assertion"])
    return b.build()


def test_classifier_returns_structured_classification():
    c = FailureClassifier().classify(_ctx(network=[{"status": 500}]))
    assert isinstance(c, Classification)
    assert c.category is FailureCategory.BACKEND
    assert c.subcategory
    assert c.reason
    assert c.owner
    assert c.risk_level == RiskLevel.CRITICAL.value
    assert 0 <= c.confidence <= 100


def test_classifier_serialisable():
    c = FailureClassifier().classify(_ctx(network=[{"status": 401}]))
    d = c.to_dict()
    assert d["category"] == "Authentication"
    assert d["risk_level"]


def test_owner_resolver_custom_override():
    resolver = OwnerResolver({FailureCategory.BACKEND: "Payments Squad"})
    assert resolver.resolve(FailureCategory.BACKEND) == "Payments Squad"
    # Unmapped category falls back to defaults.
    assert resolver.resolve(FailureCategory.NETWORK)


def test_owner_resolver_register_chaining():
    resolver = OwnerResolver().register(FailureCategory.SECURITY, "Red Team")
    assert resolver.resolve(FailureCategory.SECURITY) == "Red Team"


def test_classifier_uses_injected_owner_resolver():
    resolver = OwnerResolver({FailureCategory.AUTHENTICATION: "Identity Guild"})
    c = FailureClassifier(owner_resolver=resolver).classify(_ctx(network=[{"status": 401}]))
    assert c.owner == "Identity Guild"


def test_unknown_failure_is_medium_risk():
    c = FailureClassifier().classify(_ctx(message="totally novel error"))
    assert c.category is FailureCategory.UNKNOWN
    assert c.risk_level == RiskLevel.MEDIUM.value


@pytest.mark.parametrize(
    "text,expected",
    [
        ("no such element found", FailureCategory.ELEMENT_NOT_FOUND),
        ("database deadlock detected", FailureCategory.DATABASE),
        ("ssl certificate verify failed", FailureCategory.SECURITY),
        ("No module named 'foo'", FailureCategory.DEPENDENCY),
    ],
)
def test_new_categories_via_coerce(text, expected):
    assert FailureCategory.coerce(text) is expected
