"""Trend analytics over the last N executions.

Single responsibility: turn a run history into chart-ready series and
distributions. Pure computation; the dashboard layer decides how to draw it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .models import ExecutionRun


@dataclass
class TrendData:
    labels: list[str] = field(default_factory=list)
    pass_rate: list[float] = field(default_factory=list)
    failure_count: list[int] = field(default_factory=list)
    avg_confidence: list[float] = field(default_factory=list)
    critical: list[int] = field(default_factory=list)
    duration_s: list[float] = field(default_factory=list)
    quality_score: list[int] = field(default_factory=list)
    owner_distribution: dict[str, int] = field(default_factory=dict)
    category_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "labels": self.labels,
            "pass_rate": self.pass_rate,
            "failure_count": self.failure_count,
            "avg_confidence": self.avg_confidence,
            "critical": self.critical,
            "duration_s": self.duration_s,
            "quality_score": self.quality_score,
            "owner_distribution": self.owner_distribution,
            "category_distribution": self.category_distribution,
        }


class TrendAnalyzer:
    """Builds :class:`TrendData` for the most recent ``window`` runs."""

    def analyze(self, runs: Iterable[ExecutionRun], window: int = 10) -> TrendData:
        ordered = list(runs)[-window:]
        data = TrendData()
        owner_dist: dict[str, int] = {}
        category_dist: dict[str, int] = {}
        for run in ordered:
            data.labels.append(run.run_id.replace("run_", ""))
            data.pass_rate.append(round(run.pass_rate, 1))
            data.failure_count.append(run.failed)
            data.avg_confidence.append(round(run.avg_confidence, 1))
            data.critical.append(run.critical_count)
            data.duration_s.append(round(run.duration_s, 1))
            data.quality_score.append(run.quality_score)
            for owner, n in run.owners.items():
                owner_dist[owner] = owner_dist.get(owner, 0) + n
            for cat, n in run.categories.items():
                category_dist[cat] = category_dist.get(cat, 0) + n
        data.owner_distribution = dict(sorted(owner_dist.items(), key=lambda kv: -kv[1]))
        data.category_distribution = dict(sorted(category_dist.items(), key=lambda kv: -kv[1]))
        return data
