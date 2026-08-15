"""Shared fixtures for the GitHub Action orchestration tests.

Makes the ``aiqa_action`` package (which lives under the action folder, outside
the installed SDK) importable. Tests are marked ``action`` via the module-level
``pytestmark`` in each test file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ACTION_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".github" / "actions" / "analyze-failures" / "scripts"
)
if str(_ACTION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_ACTION_SCRIPTS))
