"""Flaky-test detection from execution history.

A test is considered flaky when its failing/not-failing pattern alternates over
recent runs (more than one transition). History stores only the set of failing
test ids per run, so "not-failing" means the test either passed or did not run —
a deliberately conservative signal that still catches classic flakiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import ExecutionRun


@dataclass
class FlakyStat:
    test_id: str = ""
    test_name: str = ""
    flaky: bool = False
    flakiness_pct: float = 0.0
    transitions: int = 0
    fail_runs: int = 0
    window: int = 0


class FlakyDetector:
    """Detects flaky tests across an ordered sequence of runs (oldest first)."""

    def detect(self, runs: Iterable[ExecutionRun], window: int = 10) -> dict[str, FlakyStat]:
        ordered = list(runs)[-window:]
        if len(ordered) < 3:
            return {}

        names: dict[str, str] = {}
        for run in ordered:
            for f in run.failures:
                names.setdefault(f.test_id, f.test_name)

        stats: dict[str, FlakyStat] = {}
        for test_id, test_name in names.items():
            # Sequence of booleans: did this test fail in each run?
            seq = [any(f.test_id == test_id for f in run.failures) for run in ordered]
            # Trim leading not-failing entries before the first observed failure.
            first = seq.index(True)
            trimmed = seq[first:]
            transitions = sum(1 for a, b in zip(trimmed, trimmed[1:]) if a != b)
            fail_runs = sum(1 for x in trimmed if x)
            win = len(trimmed)
            is_flaky = transitions >= 2 and 0 < fail_runs < win
            stats[test_id] = FlakyStat(
                test_id=test_id,
                test_name=test_name,
                flaky=is_flaky,
                flakiness_pct=round(100.0 * fail_runs / win, 1) if win else 0.0,
                transitions=transitions,
                fail_runs=fail_runs,
                window=win,
            )
        return stats

    def flaky_test_ids(self, runs: Iterable[ExecutionRun], window: int = 10) -> set[str]:
        return {tid for tid, s in self.detect(runs, window).items() if s.flaky}
