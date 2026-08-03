"""AI narrative generation — executive summaries and cross-run insights.

Deterministic, offline prose generation grounded in the aggregated execution
data. This does NOT change or re-run the AI analysis engine; it only summarises
the analysis results that already exist.
"""

from __future__ import annotations

from typing import Iterable

from .comparison import RunComparison
from .models import ExecutionRun


class ExecutiveSummaryGenerator:
    """Produces a short prose summary of a single execution."""

    def summarize(self, run: ExecutionRun, comparison: RunComparison | None = None) -> str:
        parts: list[str] = []
        if run.failed == 0:
            parts.append(
                f"All {run.total} test(s) passed on {run.framework or 'the suite'} "
                f"in the {run.environment or 'default'} environment."
            )
        else:
            parts.append(
                f"{run.failed} of {run.total} test(s) failed "
                f"(pass rate {run.pass_rate:.0f}%)."
            )
            top_cat = next(iter(run.categories), None)
            if top_cat:
                n = run.categories[top_cat]
                parts.append(
                    f"The dominant failure category is {top_cat} ({n} failure(s))."
                )
            if run.critical_count:
                parts.append(f"{run.critical_count} failure(s) are critical or blocking.")
            if run.security_count:
                parts.append(
                    f"{run.security_count} security-related (authentication/authorization) "
                    "failure(s) were detected."
                )

        parts.append(
            f"Quality score is {run.quality_score}/100 ({run.quality_band}); "
            f"build health is {run.build_health}."
        )

        if comparison and comparison.previous_run_id:
            if comparison.new_failures:
                parts.append(f"{len(comparison.new_failures)} new failure(s) versus the previous run.")
            if comparison.resolved_failures:
                parts.append(f"{len(comparison.resolved_failures)} previously failing test(s) now pass.")
            if comparison.pass_rate_change:
                direction = "up" if comparison.pass_rate_change > 0 else "down"
                parts.append(f"Pass rate is {direction} {abs(comparison.pass_rate_change):.0f} points.")

        parts.append(f"Release readiness: {run.release_readiness}.")
        return " ".join(parts)


class AIInsightsEngine:
    """Derives cross-run insights from history (trends, first-seen signals)."""

    def insights(self, runs: Iterable[ExecutionRun], window: int = 10) -> list[str]:
        ordered = list(runs)[-window:]
        if not ordered:
            return []
        out: list[str] = []
        current = ordered[-1]
        previous = ordered[-2] if len(ordered) >= 2 else None

        if previous:
            out.extend(self._category_shifts(current, previous))
            out.extend(self._first_seen_statuses(current, ordered[:-1]))
            if current.pass_rate < previous.pass_rate - 5:
                out.append(
                    f"Pass rate dropped from {previous.pass_rate:.0f}% to "
                    f"{current.pass_rate:.0f}% in the latest run."
                )
            elif current.pass_rate > previous.pass_rate + 5:
                out.append(
                    f"Pass rate improved from {previous.pass_rate:.0f}% to "
                    f"{current.pass_rate:.0f}% in the latest run."
                )

        # Persistent hotspots across the whole window.
        owner_totals: dict[str, int] = {}
        for run in ordered:
            for owner, n in run.owners.items():
                owner_totals[owner] = owner_totals.get(owner, 0) + n
        if owner_totals:
            worst_owner, count = max(owner_totals.items(), key=lambda kv: kv[1])
            if count >= 3 and worst_owner and worst_owner != "Unassigned":
                out.append(
                    f"'{worst_owner}' owns the most failures over the last "
                    f"{len(ordered)} run(s) ({count} total)."
                )

        if current.critical_count == 0 and current.failed == 0:
            out.append("No failures in the latest run — the suite is fully green.")
        return out

    def _category_shifts(self, current: ExecutionRun, previous: ExecutionRun) -> list[str]:
        out: list[str] = []
        for cat, now in current.categories.items():
            before = previous.categories.get(cat, 0)
            if before == 0 and now > 0:
                out.append(f"{cat} failures appeared for the first time in this run ({now}).")
            elif before and now > before:
                pct = round(100.0 * (now - before) / before)
                if pct >= 25:
                    out.append(f"{cat} failures increased by {pct}% ({before} → {now}).")
        for cat, before in previous.categories.items():
            if before and current.categories.get(cat, 0) == 0:
                out.append(f"{cat} failures were fully resolved ({before} → 0).")
        return out

    def _first_seen_statuses(self, current: ExecutionRun, history: list[ExecutionRun]) -> list[str]:
        seen_statuses: set[int] = set()
        for run in history:
            for f in run.failures:
                seen_statuses.update(f.http_statuses)
        out: list[str] = []
        new_statuses: set[int] = set()
        for f in current.failures:
            for s in f.http_statuses:
                if s and s not in seen_statuses:
                    new_statuses.add(s)
        for s in sorted(new_statuses):
            out.append(f"HTTP {s} failures appeared for the first time.")
        return out
