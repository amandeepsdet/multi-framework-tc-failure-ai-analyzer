"""Failure clustering by generic root-cause domain.

Groups failures into high-level clusters (Authentication, Backend, UI, Timeout,
Network, Infrastructure, Security, Other) with per-cluster statistics. Pure
computation over :class:`RunFailure` objects.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from ...core.enums import FailureCategory
from .models import RunFailure

# Map fine-grained categories to coarse clusters used across the platform.
_CLUSTER_MAP: dict[str, str] = {
    FailureCategory.AUTHENTICATION.value: "Authentication",
    FailureCategory.AUTHORIZATION.value: "Security",
    FailureCategory.BACKEND.value: "Backend",
    FailureCategory.API.value: "Backend",
    FailureCategory.UI.value: "UI",
    FailureCategory.LOCATOR.value: "UI",
    FailureCategory.BROWSER.value: "UI",
    FailureCategory.PERFORMANCE.value: "Timeout",
    FailureCategory.NETWORK.value: "Network",
    FailureCategory.INFRASTRUCTURE.value: "Infrastructure",
    FailureCategory.ENVIRONMENT.value: "Infrastructure",
    FailureCategory.CONFIGURATION.value: "Infrastructure",
}


@dataclass
class FailureCluster:
    name: str = ""
    count: int = 0
    critical: int = 0
    avg_confidence: float = 0.0
    owners: dict[str, int] = field(default_factory=dict)
    test_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "critical": self.critical,
            "avg_confidence": self.avg_confidence,
            "owners": dict(self.owners),
            "test_names": list(self.test_names),
        }


class FailureClusterer:
    """Clusters failures into coarse domains with aggregate stats."""

    @staticmethod
    def cluster_name(category: str) -> str:
        return _CLUSTER_MAP.get(category, "Other")

    def cluster(self, failures: Iterable[RunFailure]) -> list[FailureCluster]:
        buckets: dict[str, list[RunFailure]] = {}
        for f in failures:
            buckets.setdefault(self.cluster_name(f.category), []).append(f)

        clusters: list[FailureCluster] = []
        for name, items in buckets.items():
            confs = [f.confidence for f in items]
            owners: dict[str, int] = {}
            for f in items:
                owners[f.owner or "Unassigned"] = owners.get(f.owner or "Unassigned", 0) + 1
            clusters.append(
                FailureCluster(
                    name=name,
                    count=len(items),
                    critical=sum(1 for f in items if f.is_critical),
                    avg_confidence=round(sum(confs) / len(confs), 1) if confs else 0.0,
                    owners=dict(sorted(owners.items(), key=lambda kv: -kv[1])),
                    test_names=[f.test_name for f in items],
                )
            )
        clusters.sort(key=lambda c: (-c.count, c.name))
        return clusters
