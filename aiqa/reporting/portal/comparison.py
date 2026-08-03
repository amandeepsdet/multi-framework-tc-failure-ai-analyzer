"""Run-to-run comparison.

Single responsibility: diff two executions and quantify what changed —
new/resolved/persisting failures and the deltas in headline metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ExecutionRun, RunFailure


@dataclass
class RunComparison:
    current_run_id: str = ""
    previous_run_id: str = ""
    new_failures: list[dict[str, Any]] = field(default_factory=list)
    resolved_failures: list[dict[str, Any]] = field(default_factory=list)
    persisting_failures: list[dict[str, Any]] = field(default_factory=list)
    regression_pct: float = 0.0
    pass_rate_change: float = 0.0
    exec_time_diff_s: float = 0.0
    avg_confidence_diff: float = 0.0
    quality_score_diff: int = 0
    build_health_change: str = ""


class RunComparisonEngine:
    """Compares a current run against a previous one by failure signature."""

    def compare(self, current: ExecutionRun, previous: ExecutionRun | None) -> RunComparison:
        if previous is None:
            return RunComparison(
                current_run_id=current.run_id,
                previous_run_id="",
                new_failures=[self._brief(f) for f in current.failures],
                pass_rate_change=round(current.pass_rate, 1),
                exec_time_diff_s=round(current.duration_s, 1),
                avg_confidence_diff=round(current.avg_confidence, 1),
                quality_score_diff=current.quality_score,
                build_health_change=f"→ {current.build_health}",
            )

        cur_by_sig = {f.signature: f for f in current.failures}
        prev_by_sig = {f.signature: f for f in previous.failures}
        cur_sigs = set(cur_by_sig)
        prev_sigs = set(prev_by_sig)

        new = [self._brief(cur_by_sig[s]) for s in cur_sigs - prev_sigs]
        resolved = [self._brief(prev_by_sig[s]) for s in prev_sigs - cur_sigs]
        persisting = [self._brief(cur_by_sig[s]) for s in cur_sigs & prev_sigs]

        denom = previous.failed or 1
        regression_pct = round(100.0 * len(new) / denom, 1)

        health_change = (
            f"{previous.build_health} → {current.build_health}"
            if previous.build_health != current.build_health
            else current.build_health
        )

        return RunComparison(
            current_run_id=current.run_id,
            previous_run_id=previous.run_id,
            new_failures=new,
            resolved_failures=resolved,
            persisting_failures=persisting,
            regression_pct=regression_pct,
            pass_rate_change=round(current.pass_rate - previous.pass_rate, 1),
            exec_time_diff_s=round(current.duration_s - previous.duration_s, 1),
            avg_confidence_diff=round(current.avg_confidence - previous.avg_confidence, 1),
            quality_score_diff=current.quality_score - previous.quality_score,
            build_health_change=health_change,
        )

    @staticmethod
    def _brief(f: RunFailure) -> dict[str, Any]:
        return {
            "test_id": f.test_id,
            "test_name": f.test_name,
            "category": f.category,
            "severity": f.severity,
            "confidence": f.confidence,
            "owner": f.owner,
            "signature": f.signature,
            "root_cause": f.root_cause,
        }
