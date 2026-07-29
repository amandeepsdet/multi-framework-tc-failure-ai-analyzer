"""Base class and shared helpers for framework adapters.

Adapters are the *only* place that may import a specific automation framework.
They translate framework-specific state into a generic
:class:`~aiqa.core.models.FailureContext` via
:class:`~aiqa.core.context_builder.FailureContextBuilder`, so the engine remains
framework-agnostic.
"""

from __future__ import annotations

import subprocess

from ..core.context_builder import FailureContextBuilder
from ..core.interfaces import FrameworkAdapter

__all__ = ["FrameworkAdapter", "FailureContextBuilder", "git_commit"]


def git_commit() -> str:
    """Best-effort short git commit hash, or empty string."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""
