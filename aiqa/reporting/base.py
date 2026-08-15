"""Reporter base class and a registry for pluggable output formats.

Reporters consume an :class:`~aiqa.core.models.AnalysisResult` (optionally with
its :class:`~aiqa.core.models.FailureContext` for extra detail) and render it to
a string. They never touch a framework. New formats (PDF, Slack, JUnit XML) are
added by subclassing :class:`Reporter` and registering the class — no existing
code changes.
"""

from __future__ import annotations

from ..core.interfaces import Reporter

_REGISTRY: dict[str, type[Reporter]] = {}


def register_reporter(cls: type[Reporter]) -> type[Reporter]:
    """Class decorator that registers a reporter under its ``format`` key."""
    key = getattr(cls, "format", "").lower()
    if not key:
        raise ValueError(f"{cls.__name__} must define a non-empty 'format'")
    _REGISTRY[key] = cls
    return cls


def get_reporter(format: str) -> Reporter:
    """Instantiate a registered reporter by format key (e.g. ``"markdown"``)."""
    key = (format or "").lower()
    if key not in _REGISTRY:
        raise KeyError(
            f"No reporter registered for format '{format}'. "
            f"Available: {', '.join(sorted(_REGISTRY)) or 'none'}"
        )
    return _REGISTRY[key]()


def available_formats() -> list[str]:
    return sorted(_REGISTRY)
