"""In-package CLI entry point for the QA AI Assistant.

Mirrors the top-level ``qa_ai.py`` so the assistant can also be launched with
``python -m assistant.qa_ai``. All logic is delegated to
:func:`assistant.commands.run`.
"""

from __future__ import annotations

import sys

from .commands import run


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
