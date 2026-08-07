"""Root-cause analysis engine.

Given a :class:`FailureRecord`, produce a structured :class:`AnalysisResult`
(category, confidence, evidence, owner, recommended fix). Two strategies:

* **LLM strategy** — when a real provider is configured, build a prompt (with
  RAG-retrieved similar failures) and parse a strict JSON answer. Every claim
  is validated against the collected evidence so the model cannot hallucinate.
* **Heuristic strategy** — a deterministic rule engine that runs with zero
  dependencies and zero secrets. It is the default and the fallback, ensuring
  the framework always produces an analysis on a fresh setup.

Confidence is always *explained*: the ``evidence`` list references the actual
signals (HTTP status codes, console errors, empty DOM, ...) that drove the
verdict.
"""

from __future__ import annotations

import re
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .llm_client import BaseLLMClient, LLMUnavailableError, get_llm_client
from .models import AnalysisResult, Evidence, FailureCategory, FailureRecord, Severity
from .prompt_builder import PromptBuilder
from .security import scrub
from .vector_store import BaseVectorStore, get_vector_store

logger = get_logger("ai.failure_analyzer")

# Only treat a 4xx/5xx number as an HTTP status when it appears in an explicit
# HTTP context, so arbitrary 3-digit numbers in a stacktrace (line numbers,
# addresses) are not mistaken for server errors.
_HTTP_CONTEXT_RE = re.compile(r"(?:http|status|code|response|error)\D{0,10}([45]\d{2})\b", re.I)

_SYSTEM_PROMPT = (
    "You are an expert QA reliability engineer. You perform precise, evidence-"
    "grounded root-cause analysis and never fabricate information."
)

# Ownership routing by category — configurable mapping, enterprise-style.
_OWNER_MAP: dict[FailureCategory, str] = {
    FailureCategory.BACKEND: "Backend / Platform team",
    FailureCategory.API: "Backend / API team",
    FailureCategory.AUTHENTICATION: "Identity / Auth team",
    FailureCategory.AUTHORIZATION: "Identity / Auth team",
    FailureCategory.LOCATOR: "UI Automation / QA team",
    FailureCategory.UI: "Frontend team",
    FailureCategory.NETWORK: "Infrastructure / SRE team",
    FailureCategory.PERFORMANCE: "Performance / SRE team",
    FailureCategory.INFRASTRUCTURE: "Infrastructure / SRE team",
    FailureCategory.BROWSER: "UI Automation / QA team",
    FailureCategory.ENVIRONMENT: "DevOps / Environment owners",
    FailureCategory.DATA: "Data / Test-data owners",
    FailureCategory.CONFIGURATION: "QA Framework owners",
    FailureCategory.FLAKY: "QA Automation team",
    FailureCategory.UNKNOWN: "Triage / QA lead",
}


class FailureAnalyzer:
    """Analyzes a failure record into a structured, evidence-backed result."""

    def __init__(
        self,
        cfg: AIConfig = ai_config,
        llm: BaseLLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        vector_store: BaseVectorStore | None = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm or get_llm_client(cfg)
        self.prompts = prompt_builder or PromptBuilder(cfg)
        self.vector_store = vector_store or get_vector_store(cfg)

    # ------------------------------------------------------------------ public
    def analyze(self, record: FailureRecord, framework_context: str = "") -> AnalysisResult:
        """Return a root-cause analysis, using an LLM when available."""
        similar = self.retrieve_similar(record)
        if self.cfg.uses_llm and self.llm.is_available():
            try:
                return self._analyze_with_llm(record, similar, framework_context)
            except (LLMUnavailableError, Exception) as exc:  # noqa: BLE001
                logger.warning("LLM analysis failed (%s); using heuristic engine", exc)
        result = self._analyze_heuristically(record)
        result.similar_failures = similar
        return result

    def retrieve_similar(self, record: FailureRecord, top_k: int | None = None) -> list[dict[str, Any]]:
        """RAG: return the most similar past failures from the vector store."""
        try:
            hits = self.vector_store.search(record.searchable_text(), top_k or self.cfg.rag_top_k)
        except Exception as exc:  # pragma: no cover
            logger.debug("Vector search failed: %s", exc)
            return []
        return [
            {
                "test_name": hit.metadata.get("test_name", ""),
                "category": hit.metadata.get("category", ""),
                "similarity": round(hit.score * 100),
                "summary": hit.text[:160],
            }
            for hit in hits
        ]

    def index(self, record: FailureRecord, analysis: AnalysisResult) -> None:
        """Add a completed analysis to the vector store for future RAG."""
        try:
            self.vector_store.add(
                doc_id=record.record_id or record.timestamp,
                text=record.searchable_text(),
                metadata={
                    "test_name": record.test_name,
                    "category": analysis.category.value,
                    "confidence": analysis.confidence,
                    "timestamp": record.timestamp,
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.debug("Could not index failure: %s", exc)

    # -------------------------------------------------------------------- LLM
    def _analyze_with_llm(
        self, record: FailureRecord, similar: list[dict[str, Any]], framework_context: str
    ) -> AnalysisResult:
        ev = record.evidence
        masked = scrub(
            {
                "console": ev.console_logs,
                "network": ev.network,
                "api": ev.api_responses,
                "dom": ev.dom,
                "assertion": ev.assertion_message,
                "stacktrace": ev.stacktrace,
            },
            enabled=self.cfg.mask_secrets,
            mask_urls=self.cfg.mask_urls,
        )
        prompt = self.prompts.build(
            "root_cause",
            {
                "test_name": record.test_name,
                "exception_type": ev.exception_type,
                "exception_message": masked["assertion"],
                "assertion_message": masked["assertion"],
                "url": ev.url,
                "page_title": ev.page_title,
                "stacktrace": masked["stacktrace"],
                "console_logs": masked["console"],
                "network": masked["network"],
                "api_responses": masked["api"],
                "dom": masked["dom"],
                "similar_failures": similar,
                "framework_context": framework_context,
            },
        )
        data = self.llm.complete_json(prompt, system=_SYSTEM_PROMPT)
        result = AnalysisResult.from_dict(data)
        result.source = self.llm.name
        result.similar_failures = similar
        if not result.owner:
            result.owner = _OWNER_MAP.get(result.category, _OWNER_MAP[FailureCategory.UNKNOWN])
        # Ground the analysis: keep only evidence lines backed by real sources.
        result.evidence = self._ground_evidence(result.evidence, record.evidence)
        if not result.evidence:
            result.evidence = self._evidence_facts(record.evidence)
        result.confidence = max(0, min(100, result.confidence))
        return result

    # -------------------------------------------------------------- heuristic
    def _analyze_heuristically(self, record: FailureRecord) -> AnalysisResult:
        ev = record.evidence
        facts = self._evidence_facts(ev)
        category, confidence, root_cause, fix = self._classify(ev)
        severity = self._severity_for(category)
        return AnalysisResult(
            root_cause=root_cause,
            category=category,
            confidence=confidence,
            severity=severity,
            owner=_OWNER_MAP.get(category, _OWNER_MAP[FailureCategory.UNKNOWN]),
            evidence=facts,
            recommended_fix=fix,
            reasoning=(
                f"Rule-based classification from {len(facts)} evidence signal(s). "
                "Set AI_PROVIDER to an LLM for deeper natural-language analysis."
            ),
            source="heuristic",
        )

    def _classify(self, ev: Evidence) -> tuple[FailureCategory, int, str, str]:
        """Return (category, confidence, root_cause, recommended_fix)."""
        text = " ".join(
            [
                ev.exception_type,
                ev.exception_message,
                ev.assertion_message,
                ev.stacktrace[-2000:],
            ]
        ).lower()
        statuses = [n.get("status") for n in ev.network if isinstance(n.get("status"), int)]
        server_errors = [s for s in statuses if s and 500 <= s < 600]
        auth_errors = [s for s in statuses if s in (401, 403)]
        # Codes mentioned with explicit HTTP context in the free text.
        text_codes = [int(c) for c in _HTTP_CONTEXT_RE.findall(text)]
        text_5xx = [c for c in text_codes if 500 <= c < 600]

        # 1. Backend — 5xx responses are strong signals.
        if server_errors or text_5xx:
            code = server_errors[0] if server_errors else text_5xx[0]
            return (
                FailureCategory.BACKEND,
                92,
                f"A backend service returned HTTP {code}; the UI/API could not obtain valid data.",
                "Inspect server logs for the failing endpoint; the defect is server-side, not in the test.",
            )
        # 2. Authentication / Authorization.
        if 401 in auth_errors or 401 in text_codes or "unauthor" in text:
            return (
                FailureCategory.AUTHENTICATION,
                88,
                "The request was rejected as unauthenticated (HTTP 401).",
                "Verify credentials/JWT validity and that login succeeded before the protected call.",
            )
        if 403 in auth_errors or 403 in text_codes or "forbidden" in text:
            return (
                FailureCategory.AUTHORIZATION,
                86,
                "The authenticated principal lacks permission for the resource (HTTP 403).",
                "Check the account's roles/permissions for the target resource.",
            )
        # 3. Locator / element issues.
        if any(k in text for k in ("locator", "selector", "waiting for", "element is not", "no node found", "strict mode")):
            return (
                FailureCategory.LOCATOR,
                80,
                "A locator did not resolve to a visible element within the timeout.",
                "Compare the expected selector against the current DOM; the UI markup likely changed.",
            )
        # 4. Timeout / network.
        if "timeout" in text or "timed out" in text or "err_connection" in text or "econnrefused" in text:
            category = FailureCategory.NETWORK if ("connection" in text or "econnrefused" in text) else FailureCategory.PERFORMANCE
            return (
                category,
                72,
                "The operation exceeded its time budget or the host was unreachable.",
                "Check environment availability and latency; consider raising the timeout only if the app is genuinely slow.",
            )
        # 5. Blank / empty dashboard.
        if ("blank" in text or "did not render" in text or "no widgets" in text) or (ev.dom and len(ev.dom.strip()) < 200):
            return (
                FailureCategory.UI,
                70,
                "The page rendered empty or without the expected widgets.",
                "Confirm the page loaded and data-bound elements received their data; inspect console errors.",
            )
        # 6. Range / data assertions.
        if any(k in text for k in ("out of range", "outside", "not numeric", "invalid connection")):
            return (
                FailureCategory.DATA,
                68,
                "A data value fell outside its expected range or type.",
                "Validate the source data and the configured range bounds.",
            )
        # 7. Console errors present.
        if any(c.get("type") == "error" for c in ev.console_logs):
            return (
                FailureCategory.UI,
                60,
                "Browser console errors were logged during the failing step.",
                "Review the console error stack; a frontend exception likely blocked rendering.",
            )
        # 8. Unknown.
        return (
            FailureCategory.UNKNOWN,
            40,
            "Insufficient distinctive signals to classify automatically.",
            "Review the stacktrace and screenshot; enable an LLM provider for deeper analysis.",
        )

    # --------------------------------------------------------------- evidence
    @staticmethod
    def _evidence_facts(ev: Evidence) -> list[str]:
        """Produce human-readable, source-referenced evidence bullets."""
        facts: list[str] = []
        if ev.assertion_message:
            facts.append(f"Assertion: {ev.assertion_message[:200]}")
        if ev.exception_type:
            facts.append(f"Exception: {ev.exception_type}")
        statuses = sorted({n.get("status") for n in ev.network if n.get("status")})
        if statuses:
            facts.append("Network status codes observed: " + ", ".join(str(s) for s in statuses))
        errors = [c for c in ev.console_logs if c.get("type") == "error"]
        if errors:
            facts.append(f"Console errors: {len(errors)} (e.g. {errors[0].get('text', '')[:120]})")
        if ev.api_responses:
            facts.append(f"API responses captured: {len(ev.api_responses)}")
        if ev.dom:
            facts.append(f"DOM captured: {len(ev.dom)} chars")
        if ev.screenshot:
            facts.append("Screenshot captured at point of failure")
        return facts

    @staticmethod
    def _ground_evidence(claimed: list[str], ev: Evidence) -> list[str]:
        """Drop LLM evidence lines that reference sources with no data."""
        available = {s.lower() for s in ev.available_sources()}
        grounded: list[str] = []
        for line in claimed:
            low = line.lower()
            source_words = {"screenshot", "console", "network", "dom", "api", "stacktrace", "assertion"}
            referenced = source_words & set(re.findall(r"[a-z]+", low))
            if not referenced or referenced & available:
                grounded.append(line)
        return grounded

    @staticmethod
    def _severity_for(category: FailureCategory) -> Severity:
        if category in (FailureCategory.BACKEND, FailureCategory.AUTHENTICATION):
            return Severity.CRITICAL
        if category in (FailureCategory.AUTHORIZATION, FailureCategory.API, FailureCategory.NETWORK):
            return Severity.MAJOR
        if category == FailureCategory.FLAKY:
            return Severity.MINOR
        return Severity.MAJOR
