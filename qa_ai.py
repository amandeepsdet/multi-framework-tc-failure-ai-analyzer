#!/usr/bin/env python
"""Command-line entry point for the QA AI Assistant.

Examples::

    python qa_ai.py analyze-last-failure
    python qa_ai.py explain tests/test_ai_demo.py::test_demo_wrong_locator
    python qa_ai.py summarize-run
    python qa_ai.py generate-bug
    python qa_ai.py search "temperature widget failures"
    python qa_ai.py find-flaky-tests
    python qa_ai.py release-readiness
    python qa_ai.py explain-widget FuelLevel
    python qa_ai.py explain-api telemetry
    python qa_ai.py suggest-locator "Fuel Level"
    python qa_ai.py generate-test "Battery widget"
    python qa_ai.py dashboard-summary
    python qa_ai.py analyze-report reports/report.html
    python qa_ai.py ask "Why did TC-07 fail?"
    python qa_ai.py                # interactive chat mode

The heavy lifting lives in the reusable ``assistant`` package so the same
capabilities can be exposed via chat or an MCP server without change.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script (python qa_ai.py) from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_ai_engine.assistant.commands import run  # noqa: E402


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
