"""AIQA framework adapters.

Adapters are the only layer permitted to know about a specific automation
framework. Each converts framework-specific state into a generic
:class:`~aiqa.core.models.FailureContext`. Framework libraries are imported
lazily, so importing this package never requires those libraries to be present.
"""

from __future__ import annotations

from .base import FrameworkAdapter, git_commit
from .generic import GenericAdapter
from .pytest_adapter import PytestAdapter
from .robotframework import RobotFrameworkAdapter
from .selenium import SeleniumAdapter

__all__ = [
    "FrameworkAdapter",
    "git_commit",
    "GenericAdapter",
    "PytestAdapter",
    "RobotFrameworkAdapter",
    "SeleniumAdapter",
    "PlaywrightAdapter",
    "PlaywrightEventRecorder",
]


def __getattr__(name: str):
    # Lazy re-export so importing aiqa.adapters never imports the playwright
    # module's symbols unless requested.
    if name in ("PlaywrightAdapter", "PlaywrightEventRecorder"):
        from . import playwright

        return getattr(playwright, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
