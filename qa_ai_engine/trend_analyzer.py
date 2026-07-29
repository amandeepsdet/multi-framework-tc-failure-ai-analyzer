"""Trend analysis and release-readiness scoring over the failure history.

Aggregates the on-disk history into actionable insights: most common failures,
category distribution, flaky tests, most-failing APIs/widgets, average runtime,
and a day-by-day failure trend. The release-readiness scorer turns those signals
into a 0-100 score, a risk band, and a Release / Investigate / Block verdict.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .history_store import HistoryStore

logger = get_logger("ai.trend_analyzer")


@dataclass
class TrendReport:
    total_failures: int = 0
    most_common_failures: list[dict[str, Any]] = field(default_factory=list)
    category_distribution: dict[str, int] = field(default_factory=dict)
    flaky_tests: list[dict[str, Any]] = field(default_factory=list)
    most_failing_apis: list[dict[str, Any]] = field(default_factory=list)
    most_failing_widgets: list[dict[str, Any]] = field(default_factory=list)
    average_runtime_s: float | None = None
    failure_trend: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReleaseReadiness:
    score: int = 100
    risk: str = "Low"
    recommendation: str = "Release"
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrendAnalyzer:
    """Computes aggregate trends and a release-readiness verdict."""

    def __init__(self, cfg: AIConfig = ai_config, history: HistoryStore | None = None) -> None:
        self.cfg = cfg
        self.history = history or HistoryStore(cfg)

    def analyze(self) -> TrendReport:
        items = self.history.load_all()
        report = TrendReport(total_failures=len(items))
        if not items:
            return report

        categories: Counter[str] = Counter()
        tests: Counter[str] = Counter()
        apis: Counter[str] = Counter()
        widgets: Counter[str] = Counter()
        runtimes: list[float] = []
        by_day: Counter[str] = Counter()

        widget_keywords = ("fuel", "temperature", "battery", "connection", "tank", "widget")

        for item in items:
            record = item.get("record", {})
            analysis = item.get("analysis", {}) or {}
            test_name = record.get("test_name", "unknown")
            tests[test_name] += 1
            categories[analysis.get("category", "Unknown")] += 1

            meta = record.get("metadata", {})
            if isinstance(meta.get("execution_time_s"), (int, float)):
                runtimes.append(float(meta["execution_time_s"]))
            ts = (record.get("timestamp") or "")[:10]
            if ts:
                by_day[ts] += 1

            evidence = record.get("evidence", {})
            for net in evidence.get("network", []):
                status = net.get("status")
                if isinstance(status, int) and status >= 400:
                    apis[_short_url(net.get("url", ""))] += 1
            blob = (test_name + " " + record.get("failure", "")).lower()
            for kw in widget_keywords:
                if kw in blob:
                    widgets[kw] += 1

        report.category_distribution = dict(categories.most_common())
        report.most_common_failures = [{"test": t, "count": c} for t, c in tests.most_common(10)]
        report.most_failing_apis = [{"endpoint": a, "count": c} for a, c in apis.most_common(10)]
        report.most_failing_widgets = [{"widget": w, "count": c} for w, c in widgets.most_common(10)]
        report.average_runtime_s = round(sum(runtimes) / len(runtimes), 2) if runtimes else None
        report.failure_trend = dict(sorted(by_day.items()))
        report.flaky_tests = self._detect_flaky(items)
        return report

    def _detect_flaky(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flag tests classified as flaky or failing intermittently across runs."""
        per_test: dict[str, list[str]] = defaultdict(list)
        for item in items:
            record = item.get("record", {})
            analysis = item.get("analysis", {}) or {}
            per_test[record.get("test_name", "unknown")].append(analysis.get("category", "Unknown"))
        flaky: list[dict[str, Any]] = []
        for test, cats in per_test.items():
            explicit = any(c == "Flaky Test" for c in cats)
            varied = len(set(cats)) > 1 and len(cats) >= 2
            if explicit or varied:
                flaky.append(
                    {
                        "test": test,
                        "occurrences": len(cats),
                        "categories": sorted(set(cats)),
                        "confidence": 80 if explicit else 55,
                    }
                )
        return flaky

    # ----------------------------------------------------- release readiness
    def release_readiness(self, trend: TrendReport | None = None) -> ReleaseReadiness:
        trend = trend or self.analyze()
        score = 100
        rationale: list[str] = []

        critical = trend.category_distribution.get("Backend", 0) + trend.category_distribution.get(
            "Authentication", 0
        )
        if critical:
            score -= min(50, critical * 15)
            rationale.append(f"{critical} critical backend/auth failure(s) recorded.")
        if trend.total_failures:
            score -= min(25, trend.total_failures * 3)
            rationale.append(f"{trend.total_failures} total failure(s) in history.")
        if trend.flaky_tests:
            score -= min(15, len(trend.flaky_tests) * 5)
            rationale.append(f"{len(trend.flaky_tests)} flaky test(s) detected.")
        if not trend.total_failures:
            rationale.append("No failures recorded in history.")

        score = max(0, min(100, score))
        if score >= 85:
            risk, recommendation = "Low", "Release"
        elif score >= 70:
            risk, recommendation = "Medium", "Investigate"
        elif score >= 50:
            risk, recommendation = "High", "Investigate"
        else:
            risk, recommendation = "Critical", "Block Release"
        return ReleaseReadiness(score=score, risk=risk, recommendation=recommendation, rationale=rationale)


def _short_url(url: str) -> str:
    """Collapse a URL to method-agnostic endpoint path for grouping."""
    if not url:
        return "unknown"
    without_scheme = url.split("://", 1)[-1]
    path = "/" + without_scheme.split("/", 1)[1] if "/" in without_scheme else without_scheme
    return path.split("?", 1)[0]
