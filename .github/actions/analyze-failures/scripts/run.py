#!/usr/bin/env python
"""Thin entry point for the AIQA GitHub Action.

Ensures the ``aiqa_action`` orchestration package is importable, then delegates
to :func:`aiqa_action.main.main`. All logic lives in the package so it can be
unit-tested without invoking this script.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Make the sibling ``aiqa_action`` package importable when run by the runner.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# In CI the SDK is pip-installed. When running from a source checkout (local
# testing), fall back to importing ``aiqa`` from the repository root.
if importlib.util.find_spec("aiqa") is None:
    repo_root = _HERE.parents[3]  # scripts -> analyze-failures -> actions -> .github -> repo
    if (repo_root / "aiqa").is_dir():
        sys.path.insert(0, str(repo_root))

from aiqa_action.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
