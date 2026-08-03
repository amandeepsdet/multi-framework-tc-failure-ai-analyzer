"""AIQA Quality Intelligence Platform — multi-execution reporting portal.

This subpackage adds a *historical*, multi-run reporting layer on top of the
existing single-result reporters. It never modifies the core domain models, the
adapters, or the AI analysis engine — it only consumes the ``AnalysisResult``
objects the engine already produces and aggregates them into an execution
history, a knowledge base, trends and a self-contained HTML dashboard.

Public entry point::

    from aiqa.reporting.portal import QualityPortal

    portal = QualityPortal("reports")
    portal.begin_run(framework="playwright", environment="staging")
    portal.add_failure(result, context)
    run = portal.finish_run()   # -> reports/run_*/ai_report.html + reports/index.html
"""

from __future__ import annotations

from .clustering import FailureCluster, FailureClusterer
from .comparison import RunComparison, RunComparisonEngine
from .dashboard import DashboardGenerator
from .flaky import FlakyDetector, FlakyStat
from .history import ExecutionHistoryManager
from .insights import AIInsightsEngine, ExecutiveSummaryGenerator
from .knowledge_base import FailureMemory, KnowledgeBase, KnowledgeEntry
from .models import ExecutionRun, RunFailure, failure_signature
from .portal import QualityPortal
from .quality_score import QualityScore, QualityScoreCalculator
from .release_readiness import ReleaseReadiness, ReleaseReadinessEngine
from .report_builder import ExecutionReportBuilder
from .trends import TrendAnalyzer, TrendData

__all__ = [
    "QualityPortal",
    "ExecutionReportBuilder",
    "ExecutionHistoryManager",
    "RunComparisonEngine",
    "RunComparison",
    "KnowledgeBase",
    "KnowledgeEntry",
    "FailureMemory",
    "QualityScoreCalculator",
    "QualityScore",
    "TrendAnalyzer",
    "TrendData",
    "ReleaseReadinessEngine",
    "ReleaseReadiness",
    "FlakyDetector",
    "FlakyStat",
    "DashboardGenerator",
    "FailureClusterer",
    "FailureCluster",
    "AIInsightsEngine",
    "ExecutiveSummaryGenerator",
    "ExecutionRun",
    "RunFailure",
    "failure_signature",
]
