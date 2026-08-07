"""Natural-language routing and interactive chat loop for the QA Assistant.

The router maps free-text questions to :class:`QAAssistant` capabilities using
deterministic keyword intents (so it works fully offline). When an LLM provider
is configured it can additionally rephrase the grounded result into prose. The
:class:`ChatEngine` also drives the interactive REPL used by ``qa_ai.py`` with
no arguments.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from qa_ai_engine._logging import get_logger

from .assistant import QAAssistant

logger = get_logger("assistant.chat")


@dataclass
class Intent:
    """A keyword-based routing rule."""

    name: str
    patterns: list[str]
    handler: Callable[["ChatEngine", str], Any]

    def matches(self, text: str) -> bool:
        return any(re.search(p, text, re.I) for p in self.patterns)


def _extract_quoted(text: str, fallback: str = "") -> str:
    match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', text)
    if match:
        return match.group(1)
    match = re.search(r"\b(TC-?\d+|test_[a-z_]+)\b", text, re.I)
    return match.group(1) if match else fallback


class ChatEngine:
    """Routes natural language to assistant tools and runs the REPL."""

    def __init__(self, assistant: QAAssistant | None = None) -> None:
        self.assistant = assistant or QAAssistant()
        self.intents = self._build_intents()

    # --------------------------------------------------------------- routing
    def _build_intents(self) -> list[Intent]:
        a = self.assistant
        return [
            Intent("flaky", [r"\bflaky\b", r"intermittent"], lambda e, t: a.find_flaky_tests()),
            Intent("release", [r"release read", r"ready to release", r"release score", r"ship it"],
                   lambda e, t: a.release_readiness()),
            Intent("compare", [r"compare runs?", r"since last run", r"new failures", r"\bregressions?\b"],
                   lambda e, t: a.compare_runs()),
            Intent("quality", [r"quality (summary|score|overview)", r"build health", r"how healthy"],
                   lambda e, t: a.quality_summary()),
            Intent("trend", [r"fail most", r"most often", r"trend", r"take longest", r"which components",
                             r"which apis", r"sprint quality", r"executive summary"],
                   lambda e, t: a.trend_analysis()),
            Intent("bug", [r"\bbug\b", r"jira", r"azure devops", r"github issue", r"work item"],
                   lambda e, t: a.generate_bug(_extract_quoted(t) or None)),
            Intent("stacktrace", [r"stacktrace", r"traceback", r"stack trace"],
                   lambda e, t: a.explain_stacktrace(t)),
            Intent("api_resp", [r"api response", r"explain this api"],
                   lambda e, t: a.explain_api_response(t)),
            Intent("search", [r"^search\b", r"similar failures", r"show .*failures", r"historical failures",
                              r"failures from"],
                   lambda e, t: a.search(_extract_quoted(t, t))),
            Intent("explain_test", [r"why did", r"why is", r"explain .*failure", r"explain .*test", r"\bTC-?\d+\b"],
                   lambda e, t: a.explain_test(_extract_quoted(t, t))),
            Intent("summarize", [r"summariz", r"summary of", r"summarize run"],
                   lambda e, t: a.summarize_run()),
            Intent("last_failure", [r"last failure", r"latest failure", r"what failed"],
                   lambda e, t: a.analyze_last_failure()),
        ]

    def route(self, text: str) -> dict[str, Any]:
        """Return {intent, result} for a natural-language question."""
        text = (text or "").strip()
        if not text:
            return {"intent": "none", "result": {"message": "Please enter a question."}}
        for intent in self.intents:
            if intent.matches(text):
                try:
                    return {"intent": intent.name, "result": intent.handler(self, text)}
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Intent '%s' failed: %s", intent.name, exc)
                    return {"intent": intent.name, "result": {"error": str(exc)}}
        # Fallback: semantic search over history.
        return {"intent": "search", "result": self.assistant.search(text)}

    def ask(self, text: str) -> str:
        """Route and render a human-readable answer string."""
        routed = self.route(text)
        return format_result(routed["result"])

    # ------------------------------------------------------------------ REPL
    def repl(self) -> None:  # pragma: no cover - interactive
        status = self.assistant.status()
        print("=" * 68)
        print(" QA AI Assistant — interactive mode (type 'help', 'exit')")
        print(f" provider={status['provider']} | llm_available={status['llm_available']} "
              f"| history={status['history_count']}")
        print("=" * 68)
        while True:
            try:
                text = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return
            if text.lower() in {"exit", "quit", ":q"}:
                print("Bye.")
                return
            if text.lower() in {"help", "?"}:
                self._print_help()
                continue
            if not text:
                continue
            print(self.ask(text))

    def _print_help(self) -> None:  # pragma: no cover - interactive
        print("\nExample questions:")
        for tool in self.assistant.registry.all():
            ex = tool.examples()
            if ex:
                print(f"  - {ex[0]}")


def format_result(result: Any) -> str:
    """Render a tool result as readable text (JSON for structured data)."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and "markdown" in result:
        return result["markdown"]
    if isinstance(result, dict) and "code" in result:
        return result["code"]
    try:
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        return str(result)
