"""AI Failure Analysis Engine for pytest + Playwright automation projects.

An enterprise-grade, provider-agnostic engine that turns a raw test failure
(screenshot, stacktrace, DOM, console, network, API) into an evidence-grounded
root-cause analysis, a tracker-ready bug report, and quality trend / release
readiness insights — with full offline fallback and zero required secrets.

Public API::

    from qa_ai_engine import AIEngine, ai_config

    engine = AIEngine()
    if engine.enabled:
        outcome = engine.analyze_failure(test_name=..., exception=..., page=...)
        print(outcome.analysis.root_cause, outcome.analysis.confidence)
"""

from __future__ import annotations

from .ai_config import AIConfig, ai_config
from .bug_report_generator import BugReportGenerator
from .engine import AIEngine, AnalysisOutcome
from .evidence_collector import EvidenceCollector, PageEventRecorder
from .failure_analyzer import FailureAnalyzer
from .history_store import HistoryStore
from .llm_client import (
    BaseLLMClient,
    get_llm_client,
    register_provider,
)
from .locator_analyzer import LocatorAnalyzer
from .models import (
    AnalysisResult,
    BugReport,
    Evidence,
    FailureCategory,
    FailureRecord,
    Severity,
    TestMetadata,
)
from .prompt_builder import PromptBuilder
from .report_generator import ReportGenerator
from .trend_analyzer import ReleaseReadiness, TrendAnalyzer, TrendReport
from .vector_store import get_vector_store
from .visual_analyzer import VisualAnalyzer

__all__ = [
    "AIConfig",
    "ai_config",
    "AIEngine",
    "AnalysisOutcome",
    "AnalysisResult",
    "BaseLLMClient",
    "BugReport",
    "BugReportGenerator",
    "Evidence",
    "EvidenceCollector",
    "FailureAnalyzer",
    "FailureCategory",
    "FailureRecord",
    "HistoryStore",
    "LocatorAnalyzer",
    "PageEventRecorder",
    "PromptBuilder",
    "ReleaseReadiness",
    "ReportGenerator",
    "Severity",
    "TestMetadata",
    "TrendAnalyzer",
    "TrendReport",
    "VisualAnalyzer",
    "get_llm_client",
    "get_vector_store",
    "register_provider",
]

__version__ = "1.0.0"
