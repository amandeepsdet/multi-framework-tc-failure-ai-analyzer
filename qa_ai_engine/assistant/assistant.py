"""QA AI Assistant service layer.

Pure business logic decoupled from any front-end (CLI, chat, or a future MCP
server). Every capability is a plain Python method returning serialisable data,
and every method first grounds itself in retrieved context (failure history,
vector store, framework knowledge) before answering — a lightweight RAG loop.

The same :class:`QAAssistant` instance powers ``qa_ai.py`` (CLI), the
interactive chat engine, and can be wrapped by an MCP server unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from qa_ai_engine import AIEngine, FailureRecord
from qa_ai_engine._logging import get_logger

from .tool_registry import ToolRegistry

logger = get_logger("assistant.service")

# Optional, project-specific knowledge used for RAG context and offline answers.
# The library ships with a generic default. Point ``QA_AI_KNOWLEDGE_FILE`` at a
# JSON file (keys: "context", "app_name") to teach the assistant about *your*
# application, or set ``QA_AI_FRAMEWORK_CONTEXT`` / ``QA_AI_APP_NAME`` for quick
# overrides.
_DEFAULT_FRAMEWORK_CONTEXT = (
    "A test-automation project whose failures are analysed by the aiqa SDK. "
    "Tests may originate from any framework (Playwright, Selenium, Robot "
    "Framework, pytest, or anything that emits JSON). Each failure is reduced to "
    "evidence (exception, logs, network activity, artifacts) and analysed for "
    "root cause, owning team, and a suggested fix."
)


def _load_knowledge() -> tuple[str, str]:
    """Load optional project knowledge from env / a JSON file (all optional)."""
    context = os.getenv("QA_AI_FRAMEWORK_CONTEXT") or _DEFAULT_FRAMEWORK_CONTEXT
    app_name = os.getenv("QA_AI_APP_NAME", "the application under test")
    path = os.getenv("QA_AI_KNOWLEDGE_FILE")
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            context = data.get("context", context)
            app_name = data.get("app_name", app_name)
        except Exception as exc:  # noqa: BLE001 - a bad knowledge file must not crash
            logger.warning("Could not load QA_AI_KNOWLEDGE_FILE (%s): %s", path, exc)
    return context, app_name


_FRAMEWORK_CONTEXT, _APP_NAME = _load_knowledge()


class QAAssistant:
    """High-level, front-end-agnostic QA assistant."""

    def __init__(self, engine: AIEngine | None = None) -> None:
        self.engine = engine or AIEngine()
        self.history = self.engine.history
        self.registry = ToolRegistry()
        self._register_tools()

    # --------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        """Return provider/config status for the assistant."""
        return self.engine.provider_status()

    # ------------------------------------------------------- failure queries
    def analyze_last_failure(self) -> dict[str, Any]:
        """Re-analyse (or surface) the most recent stored failure."""
        latest = self.history.latest()
        if not latest:
            return {"message": "No failures found in history. Run the test suite first."}
        record = FailureRecord.from_dict(latest.get("record", {}))
        outcome = self.engine.analyze_record(
            record, framework_context=_FRAMEWORK_CONTEXT, persist=False
        )
        return {
            "test": record.test_name,
            "analysis": outcome.analysis.to_dict(),
            "bug_report": outcome.bug_report.to_dict(),
        }

    def explain_test(self, test_id: str) -> dict[str, Any]:
        """Explain why a specific test failed, using stored history + RAG."""
        matches = self.history.by_test(test_id)
        if not matches:
            similar = self.engine.search_history(test_id)
            return {
                "message": f"No stored failure for '{test_id}'.",
                "similar": similar,
                "framework_context": _FRAMEWORK_CONTEXT,
            }
        latest = matches[0]
        record = FailureRecord.from_dict(latest.get("record", {}))
        analysis = (
            latest.get("analysis")
            or self.engine.analyze_record(
                record, framework_context=_FRAMEWORK_CONTEXT, persist=False
            ).analysis.to_dict()
        )
        return {"test": record.test_name, "analysis": analysis}

    def summarize_run(self) -> dict[str, Any]:
        """Summarise the most recent run from history + trend analysis."""
        trend = self.engine.trend_report()
        readiness = self.engine.release_readiness()
        return {
            "total_failures": trend.total_failures,
            "categories": trend.category_distribution,
            "most_common": trend.most_common_failures[:5],
            "release_readiness": readiness.to_dict(),
        }

    def generate_bug(self, test_id: str | None = None) -> dict[str, Any]:
        """Generate a bug report for a given test (or the latest failure)."""
        matches = self.history.by_test(test_id) if test_id else self.history.recent(1)
        if not matches:
            return {"message": "No failure available to generate a bug report from."}
        record = FailureRecord.from_dict(matches[0].get("record", {}))
        outcome = self.engine.analyze_record(
            record, framework_context=_FRAMEWORK_CONTEXT, persist=False
        )
        markdown = self.engine.bug_gen.to_markdown(outcome.bug_report)
        return {"bug_report": outcome.bug_report.to_dict(), "markdown": markdown}

    def search(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """Semantic search across the failure history (RAG)."""
        hits = self.engine.search_history(query, top_k=top_k)
        return {"query": query, "results": hits}

    def find_flaky_tests(self) -> dict[str, Any]:
        """Return tests detected as flaky across the history."""
        return {"flaky_tests": self.engine.trend_report().flaky_tests}

    def release_readiness(self) -> dict[str, Any]:
        """Return the release-readiness score and recommendation."""
        return self.engine.release_readiness().to_dict()

    def trend_analysis(self) -> dict[str, Any]:
        """Return the full quality trend report."""
        return self.engine.trend_report().to_dict()

    # ----------------------------------------------------------- run insights
    def explain_failure(self, test_id: str) -> dict[str, Any]:
        """Explain why a specific test failed (alias for :meth:`explain_test`)."""
        return self.explain_test(test_id)

    def quality_summary(self) -> dict[str, Any]:
        """A compact quality overview: trend + readiness + top failures."""
        trend = self.engine.trend_report()
        readiness = self.engine.release_readiness()
        return {
            "total_failures": trend.total_failures,
            "categories": trend.category_distribution,
            "flaky_tests": len(trend.flaky_tests),
            "top_failures": trend.most_common_failures[:5],
            "release_readiness": readiness.to_dict(),
            "context": _FRAMEWORK_CONTEXT,
        }

    def compare_runs(self) -> dict[str, Any]:
        """Compare recent failures against older history (new vs recurring)."""
        history = self.history.load_all()
        if not history:
            return {"message": "No history to compare. Run the test suite first."}
        ordered = sorted(history, key=lambda i: i.get("record", {}).get("timestamp", ""))
        midpoint = max(1, len(ordered) // 2)
        older = {i.get("record", {}).get("test_name", "") for i in ordered[:midpoint]}
        recent = {i.get("record", {}).get("test_name", "") for i in ordered[midpoint:]}
        return {
            "new_failures": sorted(recent - older),
            "resolved_failures": sorted(older - recent),
            "persisting_failures": sorted(recent & older),
            "total_records": len(ordered),
        }

    def explain_stacktrace(self, stacktrace: str) -> dict[str, Any]:
        record = FailureRecord(test_name="ad-hoc", failure=stacktrace)
        record.evidence.stacktrace = stacktrace
        record.evidence.assertion_message = (
            stacktrace.strip().splitlines()[-1] if stacktrace.strip() else ""
        )
        outcome = self.engine.analyze_record(
            record, framework_context=_FRAMEWORK_CONTEXT, persist=False
        )
        return {"analysis": outcome.analysis.to_dict()}

    def explain_api_response(self, response_text: str) -> dict[str, Any]:
        record = FailureRecord(test_name="api-response", failure=response_text)
        record.evidence.api_responses = [{"body": response_text}]
        record.evidence.assertion_message = response_text[:300]
        outcome = self.engine.analyze_record(
            record, framework_context=_FRAMEWORK_CONTEXT, persist=False
        )
        return {"analysis": outcome.analysis.to_dict()}

    def analyze_report(self, report_path: str) -> dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            return {"message": f"Report not found: {report_path}"}
        text = path.read_text(encoding="utf-8", errors="ignore")
        failed = text.lower().count("failed")
        passed = text.lower().count("passed")
        return {
            "report": report_path,
            "approx_failed_mentions": failed,
            "approx_passed_mentions": passed,
            "trend": self.summarize_run(),
        }

    # ------------------------------------------------------------- registry
    def _register_tools(self) -> None:
        r = self.registry
        r.register_fn(
            "AnalyzeFailureTool",
            lambda **k: self.analyze_last_failure(),
            "Analyze the most recent test failure.",
            ["Why did the last test fail?"],
        )
        r.register_fn(
            "ExplainFailureTool",
            lambda test_id, **k: self.explain_failure(test_id),
            "Explain why a specific test failed.",
            ["Explain why checkout::test_pay failed"],
        )
        r.register_fn(
            "SearchHistoryTool",
            lambda query, **k: self.search(query),
            "Semantic search across failure history.",
            ["Show timeout failures"],
        )
        r.register_fn(
            "GenerateBugTool",
            lambda test_id=None, **k: self.generate_bug(test_id),
            "Generate a bug report from a failure.",
            ["Generate a bug for the last failure"],
        )
        r.register_fn(
            "SummarizeRunTool",
            lambda **k: self.summarize_run(),
            "Summarize the latest run.",
            ["Summarize the last run"],
        )
        r.register_fn(
            "CompareRunsTool",
            lambda **k: self.compare_runs(),
            "Compare recent failures against older history.",
            ["Compare the last two runs"],
        )
        r.register_fn(
            "QualitySummaryTool",
            lambda **k: self.quality_summary(),
            "Compact quality overview (trend + readiness).",
            ["Give me a quality summary"],
        )
        r.register_fn(
            "ExplainStacktraceTool",
            lambda stacktrace, **k: self.explain_stacktrace(stacktrace),
            "Explain a stacktrace.",
            ["Explain this stacktrace"],
        )
        r.register_fn(
            "ExplainAPIResponseTool",
            lambda response_text, **k: self.explain_api_response(response_text),
            "Explain an API response.",
            ["Explain this API response"],
        )
        r.register_fn(
            "ReleaseReadinessTool",
            lambda **k: self.release_readiness(),
            "Compute release-readiness score.",
            ["Are we ready to release?"],
        )
        r.register_fn(
            "TrendAnalysisTool",
            lambda **k: self.trend_analysis(),
            "Aggregate quality trend analysis.",
            ["Which tests fail most often?"],
        )
