"""Generic adapter: build a FailureContext from a plain dict or JSON.

This adapter enables *any* source — including non-Python frameworks (Cypress,
REST Assured, JUnit, NUnit, TestNG) that can emit JSON — to feed the engine. It
imports no framework at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ..core.models import FailureContext
from .base import FrameworkAdapter, git_commit


class GenericAdapter(FrameworkAdapter):
    """Builds a :class:`FailureContext` from a dict / JSON payload."""

    name = "generic"

    def collect_failure_context(
        self, payload: dict[str, Any] | str | Path, **overrides: Any
    ) -> FailureContext:
        """Accept a dict, a JSON string, or a path to a JSON file."""
        data = self._load(payload)
        context = FailureContext.from_dict(data)
        if not context.metadata.framework:
            context.metadata.framework = data.get("framework", self.name)
        if not context.metadata.git_commit:
            context.metadata.git_commit = git_commit()
        for key, value in overrides.items():
            if hasattr(context.metadata, key):
                setattr(context.metadata, key, value)
        return context

    @staticmethod
    def _load(payload: dict[str, Any] | str | Path) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, Path):
            return cast("dict[str, Any]", json.loads(payload.read_text(encoding="utf-8")))
        if isinstance(payload, str):
            candidate = Path(payload)
            if candidate.exists():
                return cast("dict[str, Any]", json.loads(candidate.read_text(encoding="utf-8")))
            return cast("dict[str, Any]", json.loads(payload))
        raise TypeError(f"Unsupported payload type: {type(payload)!r}")
