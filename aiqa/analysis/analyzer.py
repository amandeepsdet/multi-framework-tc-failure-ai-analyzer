"""The AI analysis engine.

:class:`FailureAnalyzer` is the heart of the SDK. Its contract is a single
method::

    analyze(context: FailureContext) -> AnalysisResult

It is completely framework-agnostic: it accepts only a
:class:`~aiqa.core.models.FailureContext` and never imports Playwright,
Selenium, pytest, or any application code. Language-model and similarity
backends are injected as protocol implementations (Dependency Inversion), so
the engine works fully offline by default and upgrades transparently when a
provider is supplied.
"""

from __future__ import annotations

import json
from typing import Any

from ..core.enums import FailureCategory
from ..core.interfaces import Analyzer, LLMProvider, SimilarityIndex
from ..core.models import (
    AnalysisResult,
    ConfidenceScore,
    FailureContext,
    Recommendation,
    RootCause,
    SimilarFailure,
)
from .heuristics import HeuristicClassifier, risk_for, severity_for
from .llm import OfflineProvider
from .owners import owner_for
from .rag import NullIndex
from .reasoning import ConfidenceReasoningBuilder

_SYSTEM_PROMPT = (
    "You are an expert QA reliability engineer. Perform precise, evidence-"
    "grounded root-cause analysis of an automated test failure. Never fabricate "
    "information; base every claim on the provided evidence."
)

_JSON_INSTRUCTIONS = (
    "Respond with a strict JSON object with keys: "
    '"root_cause" (object: summary, category, detail), '
    '"confidence" (object: value 0-100, rationale), '
    '"severity" (Blocker|Critical|Major|Minor|Trivial), '
    '"evidence" (array of strings), '
    '"recommendations" (array of objects: action, rationale).'
)


class FailureAnalyzer(Analyzer):
    """Analyzes a :class:`FailureContext` into an :class:`AnalysisResult`."""

    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        index: SimilarityIndex | None = None,
        classifier: HeuristicClassifier | None = None,
        owner_overrides: dict[FailureCategory, str] | None = None,
        rag_top_k: int = 3,
        record_history: bool = True,
    ) -> None:
        self.llm: LLMProvider = llm or OfflineProvider()
        self.index: SimilarityIndex = index or NullIndex()
        self.classifier = classifier or HeuristicClassifier()
        self.owner_overrides = owner_overrides
        self.rag_top_k = rag_top_k
        self.record_history = record_history

    # -- public contract ---------------------------------------------------- #
    def analyze(self, context: FailureContext) -> AnalysisResult:
        """Return a root-cause analysis for the given failure context."""
        similar = self._retrieve_similar(context)

        result: AnalysisResult
        if self._llm_available():
            try:
                result = self._analyze_with_llm(context, similar)
            except Exception:  # noqa: BLE001 - always degrade to heuristic
                result = self._analyze_heuristically(context)
        else:
            result = self._analyze_heuristically(context)

        result.similar_failures = similar
        if not result.owner:
            result.owner = owner_for(result.category, self.owner_overrides)
        if not result.risk_level:
            result.risk_level = risk_for(result.category).value
        if result.reasoning_detail is None:
            result.reasoning_detail = ConfidenceReasoningBuilder().build(
                context,
                category=result.category,
                confidence=result.confidence.value,
                similar=similar,
            )
        if self.record_history:
            self._index(context, result)
        return result

    # -- similarity / RAG --------------------------------------------------- #
    def _retrieve_similar(self, context: FailureContext) -> list[SimilarFailure]:
        try:
            hits = self.index.search(context.searchable_text(), self.rag_top_k)
        except Exception:
            return []
        return [
            SimilarFailure(
                test_name=h.get("metadata", {}).get("test_name", ""),
                category=h.get("metadata", {}).get("category", ""),
                similarity=round(float(h.get("score", 0)) * 100),
                summary=(h.get("text", "") or "")[:160],
            )
            for h in hits
        ]

    def _index(self, context: FailureContext, result: AnalysisResult) -> None:
        try:
            self.index.add(
                doc_id=context.metadata.test_id or context.test_name,
                text=context.searchable_text(),
                metadata={
                    "test_name": context.test_name,
                    "category": result.category.value,
                    "confidence": result.confidence.value,
                },
            )
        except Exception:
            pass

    # -- heuristic strategy ------------------------------------------------- #
    def _analyze_heuristically(self, context: FailureContext) -> AnalysisResult:
        verdict = self.classifier.classify(context)
        facts = self._evidence_facts(context)
        return AnalysisResult(
            root_cause=RootCause(
                summary=verdict.summary,
                category=verdict.category,
                detail=verdict.recommended_fix,
                subcategory=verdict.subcategory,
                reason=verdict.reason,
            ),
            confidence=ConfidenceScore(
                value=verdict.confidence,
                rationale=f"Rule-based classification from {len(facts)} evidence signal(s).",
            ),
            severity=severity_for(verdict.category),
            owner=owner_for(verdict.category, self.owner_overrides),
            risk_level=risk_for(verdict.category).value,
            evidence=facts,
            recommendations=[Recommendation(action=verdict.recommended_fix)],
            reasoning=(
                "Deterministic heuristic analysis. Configure an LLM provider for "
                "deeper natural-language reasoning."
            ),
            source="heuristic",
        )

    # -- LLM strategy ------------------------------------------------------- #
    def _llm_available(self) -> bool:
        try:
            return bool(self.llm) and self.llm.available()
        except Exception:
            return False

    def _analyze_with_llm(
        self, context: FailureContext, similar: list[SimilarFailure]
    ) -> AnalysisResult:
        prompt = self._build_prompt(context, similar)
        data = self.llm.complete_json(prompt, system=_SYSTEM_PROMPT)
        result = AnalysisResult.from_dict(data)
        result.source = getattr(self.llm, "name", "llm")
        # Ground the analysis: keep only evidence lines backed by real signals,
        # else fall back to the objective evidence facts.
        grounded = self._evidence_facts(context)
        if not result.evidence:
            result.evidence = grounded
        if not result.recommendations:
            result.recommendations = [Recommendation(action=result.root_cause.detail or "Investigate the failure.")]
        return result

    def _build_prompt(self, context: FailureContext, similar: list[SimilarFailure]) -> str:
        ev = context.evidence
        payload = {
            "test_name": context.metadata.test_name,
            "framework": context.metadata.framework,
            "exception_type": context.exception.type,
            "exception_message": context.exception.message,
            "assertion_message": context.assertion_message,
            "stacktrace": context.exception.stacktrace[-2000:],
            "url": context.execution.url,
            "console": [c.to_dict() for c in ev.console][:20],
            "network": [n.to_dict() for n in ev.network][:20],
            "api_responses": ev.api_responses[:10],
            "dom_excerpt": ev.dom_snapshot[:1500],
            "similar_failures": [s.to_dict() for s in similar],
        }
        return (
            f"{_JSON_INSTRUCTIONS}\n\n"
            "Analyze this test failure using only the evidence below.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    # -- evidence extraction ------------------------------------------------ #
    @staticmethod
    def _evidence_facts(context: FailureContext) -> list[str]:
        """Objective, source-referenced evidence bullets."""
        ev = context.evidence
        facts: list[str] = []
        if context.assertion_message:
            facts.append(f"Assertion: {context.assertion_message[:200]}")
        if context.exception.type:
            facts.append(f"Exception: {context.exception.type}")
        statuses = sorted({n.status for n in ev.network if n.status})
        if statuses:
            facts.append("Network status codes observed: " + ", ".join(str(s) for s in statuses))
        errors = [c for c in ev.console if c.level == "error"]
        if errors:
            facts.append(f"Console errors: {len(errors)} (e.g. {errors[0].text[:120]})")
        if ev.api_responses:
            facts.append(f"API responses captured: {len(ev.api_responses)}")
        if ev.screenshot:
            facts.append("Screenshot captured at failure.")
        if ev.dom_snapshot:
            facts.append(f"DOM snapshot captured ({len(ev.dom_snapshot)} chars).")
        return facts
