"""Example: drive the QA AI Assistant programmatically (same engine as the CLI).

The CLI (``python qa_ai.py <command>``) and chat REPL are thin front-ends over
the reusable ``QAAssistant`` service. This shows how to call it directly — handy
for embedding the assistant in your own tooling or an MCP server.

Equivalent CLI commands::

    python qa_ai.py status
    python qa_ai.py analyze-last-failure
    python qa_ai.py summarize-run
    python qa_ai.py compare-runs
    python qa_ai.py quality-summary
    python qa_ai.py release-readiness
    python qa_ai.py ask "Why did the last run fail?"

Run:
    python examples/cli_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa_ai_engine.assistant import ChatEngine, QAAssistant


def main() -> None:
    assistant = QAAssistant()

    # Structured, front-end-agnostic results (JSON-serialisable dicts):
    print("== status ==")
    print(json.dumps(assistant.status(), indent=2, default=str))

    print("\n== quality-summary ==")
    print(json.dumps(assistant.quality_summary(), indent=2, default=str))

    # Natural-language routing (works offline via keyword intents):
    print("\n== ask: 'Are we ready to release?' ==")
    print(ChatEngine(assistant).ask("Are we ready to release?"))


if __name__ == "__main__":
    main()
