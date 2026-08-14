"""Group related failures so a common root cause is reported once.

Reuses the SDK's failure signature and the aggregated ``ExecutionRun`` — it does
not compute any new similarity of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiqa.reporting.portal.models import ExecutionRun, RunFailure


@dataclass
class FailureGroup:
    category: str = ""
    root_cause: str = ""
    count: int = 0
    confidence: int = 0
    owner: str = ""
    suggested_fix: str = ""
    affected_tests: list[str] = field(default_factory=list)


def _key(f: RunFailure) -> tuple[str, str]:
    # Same category + same root-cause summary => one logical failure.
    return (f.category, (f.root_cause or "").strip().lower())


def group_failures(run: ExecutionRun | None) -> list[FailureGroup]:
    if run is None or not run.failures:
        return []
    groups: dict[tuple[str, str], FailureGroup] = {}
    for f in run.failures:
        k = _key(f)
        g = groups.get(k)
        if g is None:
            g = FailureGroup(
                category=f.category,
                root_cause=f.root_cause or f.category,
                owner=f.owner,
                suggested_fix=f.suggested_fix,
            )
            groups[k] = g
        g.count += 1
        g.confidence = max(g.confidence, f.confidence)
        if f.test_name and f.test_name not in g.affected_tests:
            g.affected_tests.append(f.test_name)
    # Most impactful (largest, then most confident) first.
    return sorted(groups.values(), key=lambda g: (g.count, g.confidence), reverse=True)
