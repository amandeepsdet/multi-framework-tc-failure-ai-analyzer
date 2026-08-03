"""Quality Intelligence Platform (portal) tests.

Validate the new multi-execution reporting subsystem end to end without
touching the core models, adapters or analysis engine.
"""

from __future__ import annotations

import json

import pytest

from aiqa import FailureAnalyzer, FailureContextBuilder
from aiqa.reporting import QualityPortal
from aiqa.reporting.portal import (
    ExecutionRun,
    FlakyDetector,
    KnowledgeBase,
    QualityScoreCalculator,
    ReleaseReadinessEngine,
    RunComparisonEngine,
    RunFailure,
    TrendAnalyzer,
    failure_signature,
)

pytestmark = pytest.mark.sdk


def _analyze(test="suite::test_login", status=500, framework="playwright", env="staging"):
    ctx = (
        FailureContextBuilder()
        .with_test(test, framework=framework)
        .with_network([{"status": status}])
        .with_execution(environment=env, browser="chromium")
        .build()
    )
    return FailureAnalyzer().analyze(ctx), ctx


# --------------------------------------------------------------------------- #
# Component-level tests
# --------------------------------------------------------------------------- #
def test_quality_score_bands():
    calc = QualityScoreCalculator()
    perfect = calc.score(pass_rate=100, avg_confidence=90)
    assert perfect.value >= 90 and perfect.band == "Excellent"
    assert perfect.build_health == "Healthy"

    bad = calc.score(pass_rate=40, critical=3, security=1)
    assert bad.value < 50 and bad.band == "Poor"
    assert bad.build_health == "Critical"


def test_release_readiness_verdicts():
    eng = ReleaseReadinessEngine()
    assert eng.assess(pass_rate=100, quality_score=95).status == "READY"
    assert eng.assess(pass_rate=100, quality_score=95, critical=1).status == "NOT READY"
    at_risk = eng.assess(pass_rate=92, quality_score=78, regressions=1)
    assert at_risk.status == "AT RISK"


def test_signature_is_stable_and_category_sensitive():
    a = failure_signature("suite::t", "Backend")
    b = failure_signature("suite::t", "Backend")
    c = failure_signature("suite::t", "Authentication")
    assert a == b and a != c


def test_comparison_new_resolved_persisting():
    prev = ExecutionRun(run_id="run_1", total=2, passed=0, failed=2)
    prev.failures = [
        RunFailure(test_id="t1", category="Backend", signature=failure_signature("t1", "Backend")),
        RunFailure(test_id="t2", category="UI", signature=failure_signature("t2", "UI")),
    ]
    prev.recompute_aggregates()
    cur = ExecutionRun(run_id="run_2", total=2, passed=1, failed=1)
    cur.failures = [
        RunFailure(test_id="t1", category="Backend", signature=failure_signature("t1", "Backend")),
        RunFailure(test_id="t3", category="Network", signature=failure_signature("t3", "Network")),
    ]
    cur.recompute_aggregates()

    cmp = RunComparisonEngine().compare(cur, prev)
    new = {f["test_id"] for f in cmp.new_failures}
    resolved = {f["test_id"] for f in cmp.resolved_failures}
    persisting = {f["test_id"] for f in cmp.persisting_failures}
    assert new == {"t3"} and resolved == {"t2"} and persisting == {"t1"}


def test_flaky_detection_alternating():
    def run(rid, failing):
        r = ExecutionRun(run_id=rid)
        r.failures = [RunFailure(test_id=t, test_name=t) for t in failing]
        return r

    runs = [
        run("run_1", ["t_flaky"]),
        run("run_2", []),
        run("run_3", ["t_flaky"]),
        run("run_4", []),
    ]
    flaky = FlakyDetector().flaky_test_ids(runs)
    assert "t_flaky" in flaky


def test_knowledge_base_records_and_recalls(tmp_path):
    kb = KnowledgeBase(tmp_path / "kb.json")
    result, ctx = _analyze()
    run = ExecutionRun(run_id="run_1", total=1, failed=1)
    run.failures = [RunFailure.from_analysis(result, ctx)]
    run.recompute_aggregates()

    memory_before = kb.recall(run.failures[0])
    assert memory_before.seen_before is False

    kb.record_run(run)
    kb2 = KnowledgeBase(tmp_path / "kb.json")  # reload from disk
    memory_after = kb2.recall(run.failures[0])
    assert memory_after.seen_before is True and memory_after.occurrences == 1


def test_trend_analyzer_series_length():
    runs = []
    for i in range(1, 4):
        r = ExecutionRun(run_id=f"run_{i}", total=10, passed=8, failed=2, quality_score=70 + i)
        r.recompute_aggregates()
        runs.append(r)
    trend = TrendAnalyzer().analyze(runs)
    assert len(trend.pass_rate) == 3 and len(trend.quality_score) == 3


# --------------------------------------------------------------------------- #
# End-to-end portal test
# --------------------------------------------------------------------------- #
def test_portal_generates_run_folder_and_dashboard(tmp_path):
    portal = QualityPortal(tmp_path)
    portal.begin_run(framework="playwright", environment="staging", browser="chromium")
    result, ctx = _analyze()
    portal.add_failure(result, ctx)
    portal.add_success("suite::test_ok")
    run = portal.finish_run()

    assert run is not None and run.total == 2 and run.failed == 1 and run.passed == 1
    assert run.quality_band and run.build_health and run.release_readiness

    run_dir = tmp_path / run.run_id
    for name in ("ai_report.html", "report.json", "report.md", "execution_summary.json"):
        assert (run_dir / name).exists(), f"missing {name}"
    assert (run_dir / "screenshots").is_dir()
    assert (run_dir / "attachments").is_dir()
    assert (run_dir / "charts").is_dir()

    index = tmp_path / "index.html"
    history = tmp_path / "history.json"
    latest = tmp_path / "latest.json"
    kb = tmp_path / "knowledge_base.json"
    assert index.exists() and history.exists() and latest.exists() and kb.exists()

    hist = json.loads(history.read_text(encoding="utf-8"))
    assert len(hist["runs"]) == 1 and hist["runs"][0]["run_id"] == run.run_id

    html = (run_dir / "ai_report.html").read_text(encoding="utf-8")
    assert "Execution Report" in html and "Failure Navigator" in html


def test_portal_second_run_updates_history_and_comparison(tmp_path):
    portal = QualityPortal(tmp_path)

    portal.begin_run(framework="pytest", environment="ci")
    r1, c1 = _analyze(test="suite::test_a", status=500)
    portal.add_failure(r1, c1)
    run1 = portal.finish_run()

    portal.begin_run(framework="pytest", environment="ci")
    r2, c2 = _analyze(test="suite::test_b", status=401)
    portal.add_failure(r2, c2)
    portal.add_success("suite::test_a")
    run2 = portal.finish_run()

    assert run1 and run2 and run1.run_id != run2.run_id
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(history["runs"]) == 2

    kb = json.loads((tmp_path / "knowledge_base.json").read_text(encoding="utf-8"))
    assert len(kb["signatures"]) >= 2


def test_portal_finish_is_idempotent(tmp_path):
    portal = QualityPortal(tmp_path)
    portal.begin_run(framework="selenium")
    result, ctx = _analyze()
    portal.add_failure(result, ctx)
    first = portal.finish_run()
    second = portal.finish_run()  # no-op
    assert first is not None and second is None

    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(history["runs"]) == 1


def test_delete_run_removes_folder_and_history(tmp_path):
    portal = QualityPortal(tmp_path)
    portal.begin_run(framework="pytest")
    result, ctx = _analyze()
    portal.add_failure(result, ctx)
    run = portal.finish_run()
    assert run is not None

    portal.delete_run(run.run_id)
    assert not (tmp_path / run.run_id).exists()
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert history["runs"] == []
