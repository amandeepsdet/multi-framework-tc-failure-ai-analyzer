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

from qa_ai_engine._logging import get_logger

from qa_ai_engine import AIEngine, FailureRecord, ai_config
from qa_ai_engine.locator_analyzer import LocatorAnalyzer

from .tool_registry import ToolRegistry

logger = get_logger("assistant.service")

# Optional, project-specific knowledge used for RAG context and offline answers.
# The library ships with a generic default. Point ``QA_AI_KNOWLEDGE_FILE`` at a
# JSON file (keys: "context", "app_name", "widgets", "apis") to teach the
# assistant about *your* application, or set ``QA_AI_FRAMEWORK_CONTEXT`` /
# ``QA_AI_APP_NAME`` for quick overrides.
_DEFAULT_FRAMEWORK_CONTEXT = (
    "A UI + API test-automation project built on Python, Pytest and Playwright "
    "(Page Object Model), commonly with Allure and pytest-html reporting. The "
    "application under test is exercised through browser UI flows and HTTP/REST "
    "API calls."
)


def _load_knowledge() -> tuple[str, dict[str, str], dict[str, str], str]:
    """Load optional project knowledge from env / a JSON file (all optional)."""
    context = os.getenv("QA_AI_FRAMEWORK_CONTEXT") or _DEFAULT_FRAMEWORK_CONTEXT
    app_name = os.getenv("QA_AI_APP_NAME", "the application under test")
    widgets: dict[str, str] = {}
    apis: dict[str, str] = {}
    path = os.getenv("QA_AI_KNOWLEDGE_FILE")
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            context = data.get("context", context)
            app_name = data.get("app_name", app_name)
            widgets = {str(k).lower(): str(v) for k, v in (data.get("widgets") or {}).items()}
            apis = {str(k).lower(): str(v) for k, v in (data.get("apis") or {}).items()}
        except Exception as exc:  # noqa: BLE001 - a bad knowledge file must not crash
            logger.warning("Could not load QA_AI_KNOWLEDGE_FILE (%s): %s", path, exc)
    return context, widgets, apis, app_name


_FRAMEWORK_CONTEXT, _WIDGET_KNOWLEDGE, _API_KNOWLEDGE, _APP_NAME = _load_knowledge()


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
        outcome = self.engine.analyze_record(record, framework_context=_FRAMEWORK_CONTEXT, persist=False)
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
        analysis = latest.get("analysis") or self.engine.analyze_record(
            record, framework_context=_FRAMEWORK_CONTEXT, persist=False
        ).analysis.to_dict()
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
        outcome = self.engine.analyze_record(record, framework_context=_FRAMEWORK_CONTEXT, persist=False)
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

    # --------------------------------------------------- knowledge / authoring
    def explain_widget(self, widget: str) -> dict[str, Any]:
        key = widget.lower().replace(" ", "")
        info = _WIDGET_KNOWLEDGE.get(key) or next(
            (v for k, v in _WIDGET_KNOWLEDGE.items() if k in key), None
        )
        failures = self.history.by_test(widget)
        return {
            "widget": widget,
            "explanation": info or f"No specific knowledge for widget '{widget}'.",
            "related_failures": len(failures),
        }

    def explain_api(self, api: str) -> dict[str, Any]:
        key = api.lower()
        info = _API_KNOWLEDGE.get(key) or next((v for k, v in _API_KNOWLEDGE.items() if k in key), None)
        return {"api": api, "explanation": info or f"No specific knowledge for API '{api}'."}

    def suggest_locator(self, description: str, dom: str | None = None) -> dict[str, Any]:
        """Suggest a Playwright locator for a UI element description."""
        if dom is None:
            latest = self.history.latest()
            dom = ((latest or {}).get("record", {}).get("evidence", {}) or {}).get("dom", "")
        if not dom:
            return {
                "message": "No DOM available. Run a UI test (which captures DOM on failure) "
                "or pass a DOM snapshot.",
                "hint": f"For '{description}', prefer stable selectors like "
                "[data-testid], [formcontrolname], or role-based getByRole.",
            }
        analysis = LocatorAnalyzer(ai_config).analyze(description, dom)
        return {"description": description, "analysis": analysis.to_dict()}

    def generate_test(self, description: str) -> dict[str, Any]:
        """Draft a pytest test skeleton for the described scenario."""
        if self.engine.llm.is_available():
            prompt = (
                f"{_FRAMEWORK_CONTEXT}\n\nWrite a single pytest test (Playwright, Page Object "
                f"Model, uses existing fixtures like dashboard_page/api_client) for: "
                f"'{description}'. Return only Python code."
            )
            try:
                return {"description": description, "code": self.engine.llm.complete(prompt)}
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM test generation failed: %s", exc)
        return {"description": description, "code": self._test_skeleton(description)}

    def dashboard_summary(self) -> dict[str, Any]:
        return {
            "application": _APP_NAME,
            "widgets": list(_WIDGET_KNOWLEDGE.values()),
            "context": _FRAMEWORK_CONTEXT,
        }

    def explain_stacktrace(self, stacktrace: str) -> dict[str, Any]:
        record = FailureRecord(test_name="ad-hoc", failure=stacktrace)
        record.evidence.stacktrace = stacktrace
        record.evidence.assertion_message = stacktrace.strip().splitlines()[-1] if stacktrace.strip() else ""
        outcome = self.engine.analyze_record(record, framework_context=_FRAMEWORK_CONTEXT, persist=False)
        return {"analysis": outcome.analysis.to_dict()}

    def explain_api_response(self, response_text: str) -> dict[str, Any]:
        record = FailureRecord(test_name="api-response", failure=response_text)
        record.evidence.api_responses = [{"body": response_text}]
        record.evidence.assertion_message = response_text[:300]
        outcome = self.engine.analyze_record(record, framework_context=_FRAMEWORK_CONTEXT, persist=False)
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

    # ------------------------------------------------------------ authoring
    @staticmethod
    def _test_skeleton(description: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in description.lower()).strip("_")[:40] or "scenario"
        return (
            '"""Auto-drafted test skeleton. Review and complete before use."""\n\n'
            "import pytest\n"
            "from playwright.sync_api import Page, expect\n\n\n"
            "@pytest.mark.ui\n"
            f"def test_{safe}(page: Page) -> None:\n"
            f'    """{description}"""\n'
            '    page.goto("/")\n'
            "    # TODO: drive the UI and assert the expected outcome for:\n"
            "    #       " + description + "\n"
            '    # e.g. expect(page.get_by_role("button", name="...")).to_be_visible()\n'
            "    assert page.title() is not None\n"
        )

    # ------------------------------------------------------------- registry
    def _register_tools(self) -> None:
        r = self.registry
        r.register_fn("AnalyzeFailureTool", lambda **k: self.analyze_last_failure(),
                      "Analyze the most recent test failure.", ["Why did the last test fail?"])
        r.register_fn("SearchHistoryTool", lambda query, **k: self.search(query),
                      "Semantic search across failure history.", ["Show timeout failures"])
        r.register_fn("GenerateBugTool", lambda test_id=None, **k: self.generate_bug(test_id),
                      "Generate a bug report from a failure.", ["Generate a bug for TC-07"])
        r.register_fn("GenerateTestTool", lambda description, **k: self.generate_test(description),
                      "Draft a pytest test for a scenario.", ["Generate a test for the login flow"])
        r.register_fn("GenerateLocatorTool", lambda description, **k: self.suggest_locator(description),
                      "Suggest a Playwright locator.", ["Suggest a locator for the login button"])
        r.register_fn("ExplainStacktraceTool", lambda stacktrace, **k: self.explain_stacktrace(stacktrace),
                      "Explain a stacktrace.", ["Explain this stacktrace"])
        r.register_fn("ExplainAPIResponseTool", lambda response_text, **k: self.explain_api_response(response_text),
                      "Explain an API response.", ["Explain this API response"])
        r.register_fn("ReleaseReadinessTool", lambda **k: self.release_readiness(),
                      "Compute release-readiness score.", ["Are we ready to release?"])
        r.register_fn("TrendAnalysisTool", lambda **k: self.trend_analysis(),
                      "Aggregate quality trend analysis.", ["Which tests fail most often?"])
        r.register_fn("DashboardUnderstandingTool", lambda **k: self.dashboard_summary(),
                      "Explain the dashboard under test.", ["Explain dashboard architecture"])
