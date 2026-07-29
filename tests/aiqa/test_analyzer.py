"""Analysis engine tests: heuristic classification, LLM fallback, RAG, DI."""

from __future__ import annotations

import pytest

from aiqa import FailureAnalyzer, FailureCategory, FailureContextBuilder, InMemoryIndex
from aiqa.analysis import OfflineProvider

pytestmark = pytest.mark.sdk


def _ctx(message="", exc_type="Error", assertion="", network=None, console=None, dom=""):
    b = FailureContextBuilder().with_test("t").with_exception_text(type=exc_type, message=message)
    if assertion:
        b.with_assertion(assertion)
    if network:
        b.with_network(network)
    if console:
        b.with_console(console)
    if dom:
        b.with_dom(dom)
    return b.build()


@pytest.mark.parametrize(
    "ctx,expected",
    [
        (_ctx(network=[{"status": 500}]), FailureCategory.BACKEND),
        (_ctx(network=[{"status": 401}]), FailureCategory.AUTHENTICATION),
        (_ctx(network=[{"status": 403}]), FailureCategory.AUTHORIZATION),
        (_ctx(message="locator #foo not found"), FailureCategory.LOCATOR),
        (_ctx(message="operation timed out after 30000ms"), FailureCategory.PERFORMANCE),
        (_ctx(message="ECONNREFUSED connection refused"), FailureCategory.NETWORK),
        (_ctx(assertion="expected 5 to equal 6"), FailureCategory.ASSERTION),
    ],
)
def test_heuristic_classification(ctx, expected):
    result = FailureAnalyzer().analyze(ctx)
    assert result.category is expected
    assert 0 <= result.confidence.value <= 100
    assert result.owner
    assert result.evidence  # grounded in real signals


def test_offline_provider_forces_heuristic():
    result = FailureAnalyzer(llm=OfflineProvider()).analyze(_ctx(network=[{"status": 500}]))
    assert result.source == "heuristic"


def test_broken_llm_provider_falls_back_to_heuristic():
    class BrokenProvider:
        name = "broken"

        def available(self):
            return True

        def complete_json(self, prompt, system=""):
            raise RuntimeError("provider exploded")

    result = FailureAnalyzer(llm=BrokenProvider()).analyze(_ctx(network=[{"status": 500}]))
    assert result.category is FailureCategory.BACKEND
    assert result.source == "heuristic"


def test_working_llm_provider_is_used():
    class FakeProvider:
        name = "fake"

        def available(self):
            return True

        def complete_json(self, prompt, system=""):
            return {
                "root_cause": {"summary": "LLM says backend", "category": "Backend"},
                "confidence": {"value": 91, "rationale": "because"},
                "severity": "Critical",
                "recommendations": [{"action": "fix server"}],
            }

    result = FailureAnalyzer(llm=FakeProvider()).analyze(_ctx(network=[{"status": 500}]))
    assert result.source == "fake"
    assert result.category is FailureCategory.BACKEND
    assert result.confidence.value == 91
    assert result.evidence  # grounded even when the model omits evidence


def test_rag_surfaces_similar_failures():
    index = InMemoryIndex()
    analyzer = FailureAnalyzer(index=index)
    analyzer.analyze(_ctx(message="backend returned http 500"))
    second = analyzer.analyze(_ctx(message="server http 500 error again"))
    assert any(s.similarity > 0 for s in second.similar_failures)
