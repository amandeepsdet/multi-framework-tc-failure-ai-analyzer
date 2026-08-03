"""QualityPortal — the orchestration facade for the Quality Intelligence Platform.

Ties the single-responsibility components together into a simple lifecycle:

    portal = QualityPortal("reports")
    portal.begin_run(framework="playwright", environment="staging")
    portal.add_failure(result, context)   # per analysed failure
    portal.add_success("suite::test_ok")  # optional, for accurate pass rate
    run = portal.finish_run()             # writes the run folder + refreshes index

Each execution produces its own ``run_*`` folder and exactly one HTML report;
the landing ``index.html`` is regenerated to discover every execution. The core
models, adapters and analysis engine are never modified.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from ...core.models import AnalysisResult, FailureContext
from .comparison import RunComparisonEngine
from .dashboard import DashboardGenerator
from .flaky import FlakyDetector
from .history import ExecutionHistoryManager
from .insights import ExecutiveSummaryGenerator
from .knowledge_base import FailureMemory, KnowledgeBase
from .models import ExecutionRun
from .quality_score import QualityScoreCalculator
from .release_readiness import ReleaseReadinessEngine
from .report_builder import ExecutionReportBuilder

_KNOWLEDGE_FILE = "knowledge_base.json"


class QualityPortal:
    """High-level API that records executions into the reports portal."""

    def __init__(self, reports_dir: Path | str | None = None):
        root = reports_dir or os.getenv("AIQA_REPORTS_DIR", "reports")
        self.root = Path(root)
        self.history = ExecutionHistoryManager(self.root)
        self.knowledge = KnowledgeBase(self.root / _KNOWLEDGE_FILE)
        self._quality = QualityScoreCalculator()
        self._readiness = ReleaseReadinessEngine()
        self._comparison = RunComparisonEngine()
        self._flaky = FlakyDetector()
        self._summary = ExecutiveSummaryGenerator()
        self._dashboard = DashboardGenerator()

        self._builder: ExecutionReportBuilder | None = None
        self._run_id: str = ""
        self._finished = False

    # -- lifecycle ---------------------------------------------------------- #
    def begin_run(
        self,
        *,
        run_name: str = "",
        framework: str = "",
        environment: str = "",
        browser: str = "",
        os_name: str = "",
        python_version: str = "",
        package_version: str = "",
        commit: str = "",
    ) -> str:
        self._run_id = self._new_run_id()
        self._finished = False
        self._builder = ExecutionReportBuilder(self.root / self._run_id, self._run_id)
        self._builder.begin(
            run_name=run_name,
            framework=framework,
            environment=environment,
            browser=browser,
            os=os_name,
            python_version=python_version,
            package_version=package_version,
            commit=commit,
        )
        return self._run_id

    def add_failure(self, result: AnalysisResult, context: FailureContext | None = None) -> None:
        self._require_active()
        assert self._builder is not None
        self._builder.add_failure(result, context)

    def add_success(self, test_id: str = "") -> None:
        self._require_active()
        assert self._builder is not None
        self._builder.add_success(test_id)

    def add_skipped(self, test_id: str = "") -> None:
        self._require_active()
        assert self._builder is not None
        self._builder.add_skipped(test_id)

    @property
    def has_data(self) -> bool:
        return bool(self._builder and self._builder.has_data)

    def finish_run(self) -> ExecutionRun | None:
        """Finalise the current run: score it, render it, update history + KB."""
        if self._builder is None or self._finished:
            return None
        self._finished = True

        run = self._builder.build_execution_run()

        previous = self.history.latest()
        comparison = self._comparison.compare(run, previous)
        run.regressions = len(comparison.new_failures) if previous else 0

        window = self.history.load() + [run]
        flaky_ids = self._flaky.flaky_test_ids(window)
        run.flaky_count = sum(1 for f in run.failures if f.test_id in flaky_ids)

        quality = self._quality.score(
            pass_rate=run.pass_rate,
            critical=run.critical_count,
            security=run.security_count,
            regressions=run.regressions,
            flaky=run.flaky_count,
            blocked=run.skipped,
            avg_confidence=run.avg_confidence,
        )
        run.quality_score = quality.value
        run.quality_band = quality.band
        run.build_health = quality.build_health

        readiness = self._readiness.assess(
            pass_rate=run.pass_rate,
            quality_score=run.quality_score,
            critical=run.critical_count,
            security=run.security_count,
            regressions=run.regressions,
        )
        run.release_readiness = readiness.status
        run.executive_summary = self._summary.summarize(run, comparison)

        # Recall memory BEFORE folding this run into the knowledge base.
        memories: dict[str, FailureMemory] = {
            f.signature: self.knowledge.recall(f) for f in run.failures
        }

        self._builder.render(run, comparison, memories)
        self.history.add_run(run)
        self.knowledge.record_run(run)
        self.regenerate_dashboard()
        return run

    # -- maintenance -------------------------------------------------------- #
    def regenerate_dashboard(self) -> Path:
        runs = self.history.load()
        return self._dashboard.generate(
            runs,
            knowledge=self.knowledge.top_recurring(),
            output_path=self.root / "index.html",
        )

    def delete_run(self, run_id: str) -> None:
        self.history.delete_run(run_id)
        self.regenerate_dashboard()

    # -- helpers ------------------------------------------------------------ #
    def _new_run_id(self) -> str:
        base = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        candidate = base
        n = 1
        while (self.root / candidate).exists():
            candidate = f"{base}_{n}"
            n += 1
        return candidate

    def _require_active(self) -> None:
        if self._builder is None:
            raise RuntimeError("begin_run() must be called before recording results")
