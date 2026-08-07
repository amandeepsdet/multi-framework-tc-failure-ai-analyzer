"""CLI command definitions for the QA AI Assistant.

Maps sub-commands to :class:`QAAssistant` service methods. Kept deliberately
thin (argument parsing only) so all real logic stays in the reusable service
layer and can be exposed elsewhere (chat, MCP) without duplication.
"""

from __future__ import annotations

import argparse
from typing import Any

from .assistant import QAAssistant
from .chat_engine import ChatEngine, format_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qa_ai",
        description="AI-powered QA assistant for framework-agnostic failure analysis.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show AI provider/config status.")
    sub.add_parser("analyze-last-failure", help="Analyze the most recent failure.")

    p_explain = sub.add_parser("explain-failure", help="Explain why a test failed.")
    p_explain.add_argument("test_id", help="Test id or node id (e.g. tests/test_x.py::test_y).")

    sub.add_parser("summarize-run", help="Summarize the latest run.")

    p_bug = sub.add_parser("generate-bug", help="Generate a bug report.")
    p_bug.add_argument("test_id", nargs="?", default=None, help="Optional test id.")

    p_search = sub.add_parser("search-history", help="Semantic search over failure history.")
    p_search.add_argument("query", help="Search query, e.g. 'login timeout failures'.")

    sub.add_parser("compare-runs", help="Compare recent failures against older history.")
    sub.add_parser("quality-summary", help="Compact quality overview (trend + readiness).")
    sub.add_parser("find-flaky-tests", help="List flaky tests.")
    sub.add_parser("release-readiness", help="Compute release-readiness score.")
    sub.add_parser("trend", help="Show quality trend analysis.")

    p_report = sub.add_parser("analyze-report", help="Analyze an HTML report.")
    p_report.add_argument("report", help="Path to reports/report.html.")

    p_ask = sub.add_parser("ask", help="Ask a natural-language question.")
    p_ask.add_argument("question", nargs="+", help="Your question.")

    sub.add_parser("chat", help="Start the interactive chat REPL.")
    return parser


def dispatch(args: argparse.Namespace, assistant: QAAssistant | None = None) -> Any:
    """Execute the parsed command and return a result payload."""
    assistant = assistant or QAAssistant()
    command = args.command

    handlers = {
        "status": lambda: assistant.status(),
        "analyze-last-failure": lambda: assistant.analyze_last_failure(),
        "explain-failure": lambda: assistant.explain_failure(args.test_id),
        "summarize-run": lambda: assistant.summarize_run(),
        "generate-bug": lambda: assistant.generate_bug(args.test_id),
        "search-history": lambda: assistant.search(args.query),
        "compare-runs": lambda: assistant.compare_runs(),
        "quality-summary": lambda: assistant.quality_summary(),
        "find-flaky-tests": lambda: assistant.find_flaky_tests(),
        "release-readiness": lambda: assistant.release_readiness(),
        "trend": lambda: assistant.trend_analysis(),
        "analyze-report": lambda: assistant.analyze_report(args.report),
        "ask": lambda: ChatEngine(assistant).ask(" ".join(args.question)),
    }
    handler = handlers.get(command)
    if handler is None:
        return None
    return handler()


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command == "chat":
        ChatEngine().repl()
        return 0

    result = dispatch(args)
    print(result if isinstance(result, str) else format_result(result))
    return 0
