"""Shared fixtures for the GitHub Action orchestration tests.

Makes the ``aiqa_action`` package (which lives under the action folder, outside
the installed SDK) importable, and marks every test in this package as ``sdk``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ACTION_SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "actions"
    / "analyze-failures"
    / "scripts"
)
if str(_ACTION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_ACTION_SCRIPTS))


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/action" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.sdk)
