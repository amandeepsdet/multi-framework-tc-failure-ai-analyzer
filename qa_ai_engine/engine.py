"""High-level façade wiring the AI engine components together.

:class:`AIEngine` is the single entry point used by pytest (``conftest.py``) and
the QA assistant. It composes the analyzer, history store, vector store, report
and bug-report generators, trend analyzer, and locator/visual analyzers via
dependency injection so any part can be swapped or mocked in tests.

The whole engine is a no-op unless ``AI_ENABLED`` is true, guaranteeing zero
impact on existing runs and full backward compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .bug_report_generator import BugReportGenerator
from .evidence_collector import EvidenceCollector, PageEventRecorder
from .failure_analyzer import FailureAnalyzer
from .history_store import HistoryStore
from .llm_client import BaseLLMClient, get_llm_client
from .locator_analyzer import LocatorAnalyzer
from .models import AnalysisResult, BugReport, FailureRecord
from .prompt_builder import PromptBuilder
from .report_generator import ReportGenerator
from .trend_analyzer import ReleaseReadiness, TrendAnalyzer, TrendReport
from .visual_analyzer import VisualAnalyzer, VisualFindings

logger = get_logger("ai.engine")

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass
class AnalysisOutcome:
    """Everything produced for a single analysed failure."""

    record: FailureRecord
    analysis: AnalysisResult
    bug_report: BugReport
    visual: VisualFindings = field(default_factory=VisualFindings)
    report_paths: dict[str, Path] = field(default_factory=dict)
    bug_paths: dict[str, Path] = field(default_factory=dict)
    history_path: Path | None = None

    @property
    def html_fragment(self) -> str:
        return ReportGenerator().to_html(self.record, self.analysis)


class AIEngine:
    """Composed, dependency-injected AI failure-analysis engine."""

    def __init__(
        self,
        cfg: AIConfig = ai_config,
        *,
        llm: BaseLLMClient | None = None,
        analyzer: FailureAnalyzer | None = None,
        history: HistoryStore | None = None,
        collector: EvidenceCollector | None = None,
        report_gen: ReportGenerator | None = None,
        bug_gen: BugReportGenerator | None = None,
        trend: TrendAnalyzer | None = None,
        locator: LocatorAnalyzer | None = None,
        visual: VisualAnalyzer | None = None,
    ) -> None:
        self.cfg = cfg
        self.cfg.ensure_dirs()
        self.llm = llm or get_llm_client(cfg)
        prompts = PromptBuilder(cfg)
        self.collector = collector or EvidenceCollector(cfg)
        self.history = history or HistoryStore(cfg)
        self.analyzer = analyzer or FailureAnalyzer(cfg, llm=self.llm, prompt_builder=prompts)
        self.report_gen = report_gen or ReportGenerator(cfg)
        self.bug_gen = bug_gen or BugReportGenerator(cfg, llm=self.llm, prompt_builder=prompts)
        self.trend = trend or TrendAnalyzer(cfg, self.history)
        self.locator = locator or LocatorAnalyzer(cfg, llm=self.llm, prompt_builder=prompts)
        self.visual = visual or VisualAnalyzer(cfg, llm=self.llm, prompt_builder=prompts)

    # ------------------------------------------------------------------ facts
    @property
    def enabled(self) -> bool:
        return self.cfg.enabled

    def provider_status(self) -> dict[str, Any]:
        return {
            "enabled": self.cfg.enabled,
            "provider": self.cfg.provider,
            "llm_available": self.llm.is_available(),
            "model": self.cfg.model,
            "vector_backend": self.cfg.vector_backend,
            "history_count": self.history.count(),
        }

    # -------------------------------------------------------- core entrypoint
    def analyze_failure(
        self,
        *,
        test_name: str,
        exception: BaseException | None = None,
        page: Any = None,
        recorder: PageEventRecorder | None = None,
        screenshot: str | None = None,
        assertion_message: str = "",
        api_responses: list[dict[str, Any]] | None = None,
        browser: str = "",
        execution_time_s: float | None = None,
        framework_context: str = "",
        persist: bool = True,
    ) -> AnalysisOutcome:
        """Collect evidence, run analysis, generate reports, and persist."""
        record = self.collector.build_record(
            test_name=test_name,
            exception=exception,
            page=page,
            recorder=recorder,
            screenshot=screenshot,
            assertion_message=assertion_message,
            api_responses=api_responses,
            browser=browser,
            execution_time_s=execution_time_s,
        )
        return self.analyze_record(record, framework_context=framework_context, persist=persist)

    def analyze_record(
        self, record: FailureRecord, *, framework_context: str = "", persist: bool = True
    ) -> AnalysisOutcome:
        """Analyse an already-built :class:`FailureRecord`."""
        analysis = self.analyzer.analyze(record, framework_context=framework_context)
        visual = self.visual.analyze(record.evidence.screenshot)
        if visual.available and visual.summary:
            analysis.evidence.append(f"Vision: {visual.summary}")
        bug = self.bug_gen.generate(record, analysis)

        outcome = AnalysisOutcome(record=record, analysis=analysis, bug_report=bug, visual=visual)
        if persist:
            stem = self._stem(record)
            outcome.history_path = self.history.save(record, analysis)
            outcome.report_paths = self.report_gen.save(record, analysis, stem)
            outcome.bug_paths = self.bug_gen.save(bug, stem)
            self.analyzer.index(record, analysis)
        return outcome

    @staticmethod
    def _stem(record: FailureRecord) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = _SAFE.sub("_", record.test_name or "unknown").strip("_")[:60]
        return f"{stamp}_{safe}"

    # ----------------------------------------------------------- convenience
    def trend_report(self) -> TrendReport:
        return self.trend.analyze()

    def release_readiness(self) -> ReleaseReadiness:
        return self.trend.release_readiness()

    def save_trend_report(self) -> dict[str, Path]:
        trend = self.trend.analyze()
        readiness = self.trend.release_readiness(trend)
        return self.report_gen.save_trend(trend, readiness)

    def search_history(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        return self.analyzer.retrieve_similar(
            FailureRecord(test_name=query, failure=query), top_k=top_k or self.cfg.rag_top_k
        )
