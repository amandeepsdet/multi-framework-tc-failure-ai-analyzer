"""Execution-level aggregation models for the Quality Intelligence Portal.

These are **new** models that describe a whole *test execution* (a run) and its
failures in a compact, JSON-serialisable form. They aggregate over the core
:class:`~aiqa.core.models.AnalysisResult` / :class:`~aiqa.core.models.FailureContext`
but never modify or replace them — the core domain is untouched.

Layering: this module depends only on the core domain and the standard library.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from ...core.enums import FailureCategory, Severity
from ...core.models import AnalysisResult, FailureContext

_CRITICAL_SEVERITIES = {Severity.BLOCKER.value, Severity.CRITICAL.value}
_SECURITY_CATEGORIES = {
    FailureCategory.AUTHENTICATION.value,
    FailureCategory.AUTHORIZATION.value,
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def failure_signature(test_id: str, category: str) -> str:
    """Stable short signature identifying a recurring failure of a test.

    Two failures of the same test in the same category share a signature so the
    knowledge base and comparison engine can recognise a recurrence.
    """
    raw = f"{(test_id or 'unknown').strip().lower()}|{(category or 'Unknown').strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class RunFailure:
    """A single analysed failure within an execution, flattened for storage."""

    test_id: str = ""
    test_name: str = ""
    suite: str = ""
    framework: str = ""
    category: str = FailureCategory.UNKNOWN.value
    severity: str = Severity.MAJOR.value
    confidence: int = 0
    owner: str = ""
    signature: str = ""
    root_cause: str = ""
    root_cause_detail: str = ""
    suggested_fix: str = ""
    reasoning: str = ""
    source: str = "heuristic"
    exception_type: str = ""
    exception_message: str = ""
    assertion_message: str = ""
    http_statuses: list[int] = field(default_factory=list)
    locator: str = ""
    environment: str = ""
    browser: str = ""
    url: str = ""
    evidence: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    recommendations: list[dict[str, str]] = field(default_factory=list)
    similar_failures: list[dict[str, Any]] = field(default_factory=list)
    screenshot: str | None = None
    attachments: dict[str, str] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.severity in _CRITICAL_SEVERITIES

    @property
    def is_security(self) -> bool:
        return self.category in _SECURITY_CATEGORIES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunFailure:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    @classmethod
    def from_analysis(
        cls,
        result: AnalysisResult,
        context: FailureContext | None = None,
    ) -> RunFailure:
        rc = result.root_cause
        test_id = context.metadata.test_id if context else ""
        test_name = context.test_name if context else "unknown"
        category = rc.category.value
        statuses = [n.status for n in context.evidence.network if n.status] if context else []
        locator = ""
        if context and context.evidence.custom:
            locator = str(
                context.evidence.custom.get("locator")
                or context.evidence.custom.get("selector")
                or ""
            )
        return cls(
            test_id=test_id or test_name,
            test_name=test_name,
            suite=context.metadata.suite if context else "",
            framework=context.metadata.framework if context else "",
            category=category,
            severity=result.severity.value,
            confidence=result.confidence.value,
            owner=result.owner or "Unassigned",
            signature=failure_signature(test_id or test_name, category),
            root_cause=rc.summary,
            root_cause_detail=rc.detail,
            suggested_fix=(
                result.recommendations[0].action if result.recommendations else rc.detail
            ),
            reasoning=result.reasoning,
            source=result.source,
            exception_type=context.exception.type if context else "",
            exception_message=context.exception.message if context else "",
            assertion_message=context.assertion_message if context else "",
            http_statuses=[int(s) for s in statuses],
            locator=locator,
            environment=context.execution.environment if context else "",
            browser=context.execution.browser if context else "",
            url=context.execution.url if context else "",
            evidence=list(result.evidence),
            evidence_sources=(context.evidence.available_sources() if context else []),
            recommendations=[r.to_dict() for r in result.recommendations],
            similar_failures=[s.to_dict() for s in result.similar_failures],
            screenshot=(context.evidence.screenshot if context else None),
            attachments=(dict(context.evidence.artifacts) if context else {}),
        )


@dataclass
class ExecutionRun:
    """Aggregated summary of one full test execution."""

    run_id: str = ""
    run_name: str = ""
    started: str = field(default_factory=utc_now_iso)
    finished: str = ""
    duration_s: float = 0.0
    framework: str = ""
    environment: str = ""
    browser: str = ""
    os: str = ""
    python_version: str = ""
    package_version: str = ""
    commit: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    avg_confidence: float = 0.0
    quality_score: int = 0
    quality_band: str = ""
    build_health: str = ""
    release_readiness: str = ""
    regressions: int = 0
    flaky_count: int = 0
    executive_summary: str = ""
    categories: dict[str, int] = field(default_factory=dict)
    owners: dict[str, int] = field(default_factory=dict)
    severities: dict[str, int] = field(default_factory=dict)
    failures: list[RunFailure] = field(default_factory=list)
    report_rel: str = ""

    # -- derived counters --------------------------------------------------- #
    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.failures if f.is_critical)

    @property
    def security_count(self) -> int:
        return sum(1 for f in self.failures if f.is_security)

    @property
    def signatures(self) -> set[str]:
        return {f.signature for f in self.failures}

    def recompute_aggregates(self) -> None:
        """Recompute pass rate, distributions and averages from raw counts."""
        self.pass_rate = round(100.0 * self.passed / self.total, 1) if self.total else 0.0
        confs = [f.confidence for f in self.failures]
        self.avg_confidence = round(sum(confs) / len(confs), 1) if confs else 0.0
        self.categories = _count_by(self.failures, lambda f: f.category)
        self.owners = _count_by(self.failures, lambda f: f.owner or "Unassigned")
        self.severities = _count_by(self.failures, lambda f: f.severity)

    def to_summary_dict(self) -> dict[str, Any]:
        """Lightweight record for history.json (includes failure signatures)."""
        return {
            "run_id": self.run_id,
            "run_name": self.run_name,
            "started": self.started,
            "finished": self.finished,
            "duration_s": self.duration_s,
            "framework": self.framework,
            "environment": self.environment,
            "browser": self.browser,
            "os": self.os,
            "python_version": self.python_version,
            "package_version": self.package_version,
            "commit": self.commit,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "pass_rate": self.pass_rate,
            "avg_confidence": self.avg_confidence,
            "quality_score": self.quality_score,
            "quality_band": self.quality_band,
            "build_health": self.build_health,
            "release_readiness": self.release_readiness,
            "regressions": self.regressions,
            "flaky_count": self.flaky_count,
            "critical": self.critical_count,
            "security": self.security_count,
            "categories": dict(self.categories),
            "owners": dict(self.owners),
            "severities": dict(self.severities),
            "report_rel": self.report_rel,
            "failures": [
                {
                    "test_id": f.test_id,
                    "test_name": f.test_name,
                    "category": f.category,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "owner": f.owner,
                    "signature": f.signature,
                    "root_cause": f.root_cause,
                }
                for f in self.failures
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """Full record (used for execution_summary.json / report.json)."""
        data = self.to_summary_dict()
        data["failures"] = [f.to_dict() for f in self.failures]
        data["executive_summary"] = self.executive_summary
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionRun:
        scalar = {
            k: data[k]
            for k in cls.__dataclass_fields__
            if k in data and k not in ("failures", "categories", "owners", "severities")
        }
        run = cls(**scalar)
        run.categories = dict(data.get("categories") or {})
        run.owners = dict(data.get("owners") or {})
        run.severities = dict(data.get("severities") or {})
        run.failures = [RunFailure.from_dict(f) for f in (data.get("failures") or [])]
        return run


def _count_by(items, key) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        k = key(item)
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
