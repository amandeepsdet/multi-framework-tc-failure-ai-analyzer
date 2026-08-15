"""Core domain models for AIQA.

These are **pure** dataclasses that describe a test failure and its analysis in
framework-agnostic terms. They must never import Playwright, Selenium, pytest,
or any application-specific code. Everything here is JSON-serialisable so a
:class:`FailureContext` can be produced by *any* adapter (even a non-Python one
writing JSON) and consumed by the engine unchanged.

Layering rule: this module is the bottom of the dependency graph. Adapters,
the analysis engine, and reporters all depend on it; it depends on nothing but
the standard library and :mod:`aiqa.core.enums`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .enums import FailureCategory, Severity


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


# --------------------------------------------------------------------------- #
# Evidence primitives
# --------------------------------------------------------------------------- #
@dataclass
class ExceptionInfo:
    """The exception/error that caused the failure, as plain text."""

    type: str = ""
    message: str = ""
    stacktrace: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkEvent:
    """A single captured network exchange (HTTP or otherwise)."""

    method: str = ""
    url: str = ""
    status: int | None = None
    duration_ms: float | None = None
    request_body: str | None = None
    response_body: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsoleMessage:
    """A client/console log line (browser console, app logger, etc.)."""

    level: str = "log"  # log | info | warning | error | debug
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LogEntry:
    """A generic log record from the system under test or the runner."""

    level: str = "info"
    message: str = ""
    source: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    """All raw signals collected at failure time, framework-agnostic.

    Every field is optional so a UI test, an API test, or a unit test can each
    populate only what applies. ``custom`` is an open extension point for any
    adapter-specific evidence that does not fit the standard fields.
    """

    screenshot: str | None = None
    dom_snapshot: str = ""
    console: list[ConsoleMessage] = field(default_factory=list)
    network: list[NetworkEvent] = field(default_factory=list)
    api_responses: list[dict[str, Any]] = field(default_factory=list)
    logs: list[LogEntry] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)  # name -> path/uri
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "screenshot": self.screenshot,
            "dom_snapshot": self.dom_snapshot,
            "console": [c.to_dict() for c in self.console],
            "network": [n.to_dict() for n in self.network],
            "api_responses": list(self.api_responses),
            "logs": [entry.to_dict() for entry in self.logs],
            "artifacts": dict(self.artifacts),
            "custom": dict(self.custom),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            screenshot=data.get("screenshot"),
            dom_snapshot=data.get("dom_snapshot", ""),
            console=[_console_from(c) for c in (data.get("console") or [])],
            network=[_network_from(n) for n in (data.get("network") or [])],
            api_responses=list(data.get("api_responses") or []),
            logs=[_log_from(entry) for entry in (data.get("logs") or [])],
            artifacts=dict(data.get("artifacts") or {}),
            custom=dict(data.get("custom") or {}),
        )

    def available_sources(self) -> list[str]:
        """Human-readable names of evidence sources that actually hold data."""
        sources: list[str] = []
        if self.screenshot:
            sources.append("Screenshot")
        if self.dom_snapshot:
            sources.append("DOM")
        if self.console:
            sources.append("Console")
        if self.network:
            sources.append("Network")
        if self.api_responses:
            sources.append("API")
        if self.logs:
            sources.append("Logs")
        if self.artifacts:
            sources.append("Artifacts")
        if self.custom:
            sources.append("Custom")
        return sources


def _console_from(data: Any) -> ConsoleMessage:
    if isinstance(data, ConsoleMessage):
        return data
    if isinstance(data, dict):
        return ConsoleMessage(
            level=data.get("level") or data.get("type") or "log", text=data.get("text", "")
        )
    return ConsoleMessage(text=str(data))


def _network_from(data: Any) -> NetworkEvent:
    if isinstance(data, NetworkEvent):
        return data
    if isinstance(data, dict):
        known = {k: data[k] for k in NetworkEvent.__dataclass_fields__ if k in data}
        return NetworkEvent(**known)
    return NetworkEvent(url=str(data))


def _log_from(data: Any) -> LogEntry:
    if isinstance(data, LogEntry):
        return data
    if isinstance(data, dict):
        known = {k: data[k] for k in LogEntry.__dataclass_fields__ if k in data}
        return LogEntry(**known)
    return LogEntry(message=str(data))


# --------------------------------------------------------------------------- #
# Context primitives
# --------------------------------------------------------------------------- #
@dataclass
class ExecutionContext:
    """Where and how the test ran — environment, not identity."""

    environment: str = ""
    browser: str = ""
    os: str = ""
    platform: str = ""
    url: str = ""
    page_title: str = ""
    timestamp: str = field(default_factory=_utc_now)
    configuration: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionContext:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


@dataclass
class FailureMetadata:
    """Identity of the failing test, framework-agnostic."""

    test_id: str = ""
    test_name: str = ""
    suite: str = ""
    framework: str = ""
    framework_version: str = ""
    tags: list[str] = field(default_factory=list)
    execution_time_s: float | None = None
    git_commit: str = ""
    retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureMetadata:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


@dataclass
class FailureContext:
    """The single, framework-agnostic input to the analysis engine.

    An adapter (Playwright, Selenium, pytest, Robot Framework, or a raw JSON
    payload) is responsible for producing this object. The AI engine consumes
    *only* this type and never learns where it came from.
    """

    metadata: FailureMetadata = field(default_factory=FailureMetadata)
    exception: ExceptionInfo = field(default_factory=ExceptionInfo)
    evidence: Evidence = field(default_factory=Evidence)
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    assertion_message: str = ""

    # -- convenience -------------------------------------------------------- #
    @property
    def test_name(self) -> str:
        return self.metadata.test_name or self.metadata.test_id or "unknown"

    def searchable_text(self) -> str:
        """Compact text used for similarity search / embeddings."""
        parts = [
            self.metadata.test_name,
            self.assertion_message,
            self.exception.type,
            self.exception.message,
        ]
        statuses = [str(n.status) for n in self.evidence.network if n.status]
        if statuses:
            parts.append("HTTP " + " ".join(sorted(set(statuses))))
        return "\n".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "exception": self.exception.to_dict(),
            "evidence": self.evidence.to_dict(),
            "execution": self.execution.to_dict(),
            "assertion_message": self.assertion_message,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureContext:
        return cls(
            metadata=FailureMetadata.from_dict(data.get("metadata", {}) or {}),
            exception=ExceptionInfo(
                **{
                    k: v
                    for k, v in (data.get("exception", {}) or {}).items()
                    if k in ExceptionInfo.__dataclass_fields__
                }
            ),
            evidence=Evidence.from_dict(data.get("evidence", {}) or {}),
            execution=ExecutionContext.from_dict(data.get("execution", {}) or {}),
            assertion_message=data.get("assertion_message", ""),
        )

    @classmethod
    def from_json(cls, text: str) -> FailureContext:
        return cls.from_dict(json.loads(text))


# --------------------------------------------------------------------------- #
# Analysis result models
# --------------------------------------------------------------------------- #
@dataclass
class ConfidenceScore:
    """A 0-100 confidence value with an explanation of how it was reached."""

    value: int = 0
    rationale: str = ""

    def __post_init__(self) -> None:
        self.value = max(0, min(100, int(self.value)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConfidenceReasoning:
    """Transparent, evidence-grounded explanation of a confidence score.

    Makes every AI conclusion explainable rather than a black box: which signals
    supported the verdict, which (if any) conflicted, and — when confidence is
    low — *why* it is low. Purely descriptive and JSON-serialisable.
    """

    confidence: int = 0
    reasoning_points: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    conflicting_evidence: list[str] = field(default_factory=list)
    assessment: str = ""
    low_confidence_note: str = ""

    def __post_init__(self) -> None:
        self.confidence = max(0, min(100, int(self.confidence)))

    @property
    def level(self) -> str:
        if self.confidence >= 85:
            return "High"
        if self.confidence >= 60:
            return "Medium"
        return "Low"

    @property
    def badge(self) -> str:
        return {"High": "🟢 High", "Medium": "🟡 Medium", "Low": "🔴 Low"}[self.level]

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "level": self.level,
            "badge": self.badge,
            "reasoning_points": list(self.reasoning_points),
            "supporting_evidence": list(self.supporting_evidence),
            "conflicting_evidence": list(self.conflicting_evidence),
            "assessment": self.assessment,
            "low_confidence_note": self.low_confidence_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfidenceReasoning:
        return cls(
            confidence=int(data.get("confidence", 0) or 0),
            reasoning_points=list(data.get("reasoning_points") or []),
            supporting_evidence=list(data.get("supporting_evidence") or []),
            conflicting_evidence=list(data.get("conflicting_evidence") or []),
            assessment=data.get("assessment", ""),
            low_confidence_note=data.get("low_confidence_note", ""),
        )


@dataclass
class RootCause:
    """The diagnosed cause of the failure."""

    summary: str = ""
    category: FailureCategory = FailureCategory.UNKNOWN
    detail: str = ""
    subcategory: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "category": self.category.value,
            "detail": self.detail,
            "subcategory": self.subcategory,
            "reason": self.reason,
        }


@dataclass
class Recommendation:
    """A concrete, actionable next step."""

    action: str = ""
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimilarFailure:
    """A related past failure surfaced by similarity search."""

    test_name: str = ""
    category: str = ""
    similarity: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    """Structured output of the AI engine — the only input reporters consume."""

    root_cause: RootCause = field(default_factory=RootCause)
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)
    severity: Severity = Severity.MAJOR
    owner: str = ""
    evidence: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    similar_failures: list[SimilarFailure] = field(default_factory=list)
    reasoning: str = ""
    source: str = "heuristic"  # "heuristic" | provider name
    risk_level: str = ""
    reasoning_detail: ConfidenceReasoning | None = None

    # -- convenience accessors --------------------------------------------- #
    @property
    def category(self) -> FailureCategory:
        return self.root_cause.category

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause.to_dict(),
            "confidence": self.confidence.to_dict(),
            "severity": self.severity.value,
            "owner": self.owner,
            "evidence": list(self.evidence),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "similar_failures": [s.to_dict() for s in self.similar_failures],
            "reasoning": self.reasoning,
            "source": self.source,
            "risk_level": self.risk_level,
            "reasoning_detail": self.reasoning_detail.to_dict() if self.reasoning_detail else None,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisResult:
        rc = data.get("root_cause", {}) or {}
        conf = data.get("confidence", {}) or {}
        if isinstance(conf, (int, float)):
            conf = {"value": int(conf)}
        return cls(
            root_cause=RootCause(
                summary=(
                    rc.get("summary", data.get("root_cause_summary", ""))
                    if isinstance(rc, dict)
                    else str(rc)
                ),
                category=FailureCategory.coerce(
                    rc.get("category") if isinstance(rc, dict) else data.get("category")
                ),
                detail=rc.get("detail", "") if isinstance(rc, dict) else "",
                subcategory=rc.get("subcategory", "") if isinstance(rc, dict) else "",
                reason=rc.get("reason", "") if isinstance(rc, dict) else "",
            ),
            confidence=ConfidenceScore(
                value=int(conf.get("value", 0) or 0),
                rationale=conf.get("rationale", ""),
            ),
            severity=Severity.coerce(data.get("severity")),
            owner=data.get("owner", ""),
            evidence=list(data.get("evidence", []) or []),
            recommendations=[
                (
                    r
                    if isinstance(r, Recommendation)
                    else (
                        Recommendation(action=r.get("action", ""), rationale=r.get("rationale", ""))
                        if isinstance(r, dict)
                        else Recommendation(action=str(r))
                    )
                )
                for r in (data.get("recommendations", []) or [])
            ],
            similar_failures=[
                (
                    s
                    if isinstance(s, SimilarFailure)
                    else SimilarFailure(
                        **{k: v for k, v in s.items() if k in SimilarFailure.__dataclass_fields__}
                    )
                )
                for s in (data.get("similar_failures", []) or [])
                if isinstance(s, (dict, SimilarFailure))
            ],
            reasoning=data.get("reasoning", ""),
            source=data.get("source", "heuristic"),
            risk_level=data.get("risk_level", ""),
            reasoning_detail=(
                ConfidenceReasoning.from_dict(data["reasoning_detail"])
                if isinstance(data.get("reasoning_detail"), dict)
                else None
            ),
        )


@dataclass
class BugReport:
    """A tracker-ready bug report derived purely from an AnalysisResult."""

    title: str = ""
    description: str = ""
    environment: str = ""
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    evidence: list[str] = field(default_factory=list)
    severity: str = Severity.MAJOR.value
    priority: str = "P2"
    owner: str = ""
    root_cause: str = ""
    suggested_fix: str = ""
    # -- extended (intelligent bug generator) fields; all optional --------- #
    summary: str = ""
    category: str = ""
    subcategory: str = ""
    framework: str = ""
    browser: str = ""
    os: str = ""
    python_version: str = ""
    build: str = ""
    commit: str = ""
    stacktrace: str = ""
    logs: list[str] = field(default_factory=list)
    network: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    preventive_action: str = ""
    risk: str = ""
    confidence: int = 0
    ai_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
