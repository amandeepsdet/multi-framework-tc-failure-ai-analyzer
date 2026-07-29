"""Typed data models shared across the AI engine.

Keeping these as plain dataclasses (rather than dicts) gives the engine a
stable, self-documenting contract, easy JSON (de)serialisation for the failure
history store, and unit-test friendliness.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FailureCategory(str, Enum):
    """Canonical root-cause categories the analyzer may assign."""

    UI = "UI"
    BACKEND = "Backend"
    API = "API"
    AUTHENTICATION = "Authentication"
    AUTHORIZATION = "Authorization"
    LOCATOR = "Locator"
    NETWORK = "Network"
    PERFORMANCE = "Performance"
    INFRASTRUCTURE = "Infrastructure"
    BROWSER = "Browser"
    ENVIRONMENT = "Environment"
    DATA = "Data"
    CONFIGURATION = "Configuration"
    FLAKY = "Flaky Test"
    UNKNOWN = "Unknown"

    @classmethod
    def coerce(cls, value: str | "FailureCategory | None") -> "FailureCategory":
        """Best-effort coercion of arbitrary text to a known category."""
        if isinstance(value, cls):
            return value
        if not value:
            return cls.UNKNOWN
        needle = str(value).strip().lower()
        for member in cls:
            if member.value.lower() == needle or member.name.lower() == needle:
                return member
        # Loose keyword mapping for LLM free-text answers.
        keywords = {
            cls.AUTHENTICATION: ("auth", "login", "credential", "401"),
            cls.AUTHORIZATION: ("forbidden", "permission", "403"),
            cls.BACKEND: ("server", "500", "backend", "database"),
            cls.LOCATOR: ("locator", "selector", "element not found", "not found"),
            cls.NETWORK: ("network", "timeout", "connection", "dns"),
            cls.PERFORMANCE: ("slow", "performance", "latency"),
            cls.FLAKY: ("flaky", "intermittent", "race"),
            cls.API: ("api", "endpoint", "rest"),
            cls.UI: ("ui", "render", "widget", "dashboard"),
        }
        for member, hints in keywords.items():
            if any(hint in needle for hint in hints):
                return member
        return cls.UNKNOWN


class Severity(str, Enum):
    BLOCKER = "Blocker"
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    TRIVIAL = "Trivial"


@dataclass
class NetworkRecord:
    """A single captured HTTP exchange during a test."""

    method: str = ""
    url: str = ""
    status: int | None = None
    duration_ms: float | None = None
    request_body: str | None = None
    response_body: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    """All raw signals collected when a test fails.

    Mirrors the "Failure JSON" contract in the specification. Optional fields
    default to empty so partial collection (e.g. an API-only test with no page)
    still produces a valid record.
    """

    screenshot: str | None = None
    stacktrace: str = ""
    exception_type: str = ""
    exception_message: str = ""
    assertion_message: str = ""
    url: str = ""
    page_title: str = ""
    dom: str = ""
    console_logs: list[dict[str, Any]] = field(default_factory=list)
    network: list[dict[str, Any]] = field(default_factory=list)
    api_responses: list[dict[str, Any]] = field(default_factory=list)
    trace_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    def available_sources(self) -> list[str]:
        """Return the names of evidence sources that actually hold data."""
        sources: list[str] = []
        if self.screenshot:
            sources.append("Screenshot")
        if self.stacktrace:
            sources.append("Stacktrace")
        if self.assertion_message:
            sources.append("Assertion")
        if self.dom:
            sources.append("DOM")
        if self.console_logs:
            sources.append("Console")
        if self.network:
            sources.append("Network")
        if self.api_responses:
            sources.append("API")
        if self.trace_path:
            sources.append("Trace")
        return sources


@dataclass
class TestMetadata:
    """Contextual metadata describing the environment of the execution."""

    test_name: str = ""
    browser: str = ""
    environment: str = ""
    timestamp: str = ""
    execution_time_s: float | None = None
    os: str = ""
    python_version: str = ""
    git_commit: str = ""
    framework_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureRecord:
    """A single stored execution failure (the unit of the history database)."""

    test_name: str
    failure: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence: Evidence = field(default_factory=Evidence)
    metadata: TestMetadata = field(default_factory=TestMetadata)
    config: dict[str, Any] = field(default_factory=dict)
    record_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "test_name": self.test_name,
            "failure": self.failure,
            "timestamp": self.timestamp,
            "evidence": self.evidence.to_dict(),
            "metadata": self.metadata.to_dict(),
            "config": self.config,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureRecord":
        return cls(
            record_id=data.get("record_id", ""),
            test_name=data.get("test_name", ""),
            failure=data.get("failure", ""),
            timestamp=data.get("timestamp", ""),
            evidence=Evidence.from_dict(data.get("evidence", {}) or {}),
            metadata=TestMetadata(**{
                k: v for k, v in (data.get("metadata", {}) or {}).items()
                if k in TestMetadata.__dataclass_fields__
            }),
            config=data.get("config", {}) or {},
        )

    def searchable_text(self) -> str:
        """Compact text representation used for embedding / vector search."""
        parts = [
            self.test_name,
            self.failure,
            self.evidence.exception_type,
            self.evidence.exception_message,
            self.evidence.assertion_message,
        ]
        statuses = [str(n.get("status")) for n in self.evidence.network if n.get("status")]
        if statuses:
            parts.append("HTTP " + " ".join(statuses))
        return "\n".join(p for p in parts if p)


@dataclass
class AnalysisResult:
    """Structured output of a root-cause analysis."""

    root_cause: str = ""
    category: FailureCategory = FailureCategory.UNKNOWN
    confidence: int = 0
    severity: Severity = Severity.MAJOR
    owner: str = ""
    evidence: list[str] = field(default_factory=list)
    recommended_fix: str = ""
    similar_failures: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    source: str = "heuristic"  # "heuristic" | provider name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["severity"] = self.severity.value
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisResult":
        return cls(
            root_cause=data.get("root_cause", ""),
            category=FailureCategory.coerce(data.get("category")),
            confidence=int(data.get("confidence", 0) or 0),
            severity=_coerce_severity(data.get("severity")),
            owner=data.get("owner", ""),
            evidence=list(data.get("evidence", []) or []),
            recommended_fix=data.get("recommended_fix", ""),
            similar_failures=list(data.get("similar_failures", []) or []),
            reasoning=data.get("reasoning", ""),
            source=data.get("source", "heuristic"),
        )


def _coerce_severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    if not value:
        return Severity.MAJOR
    needle = str(value).strip().lower()
    for member in Severity:
        if member.value.lower() == needle or member.name.lower() == needle:
            return member
    return Severity.MAJOR


@dataclass
class BugReport:
    """A generated, tracker-ready bug report."""

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
