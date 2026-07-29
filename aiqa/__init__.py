"""AIQA — an AI-powered Quality Engineering SDK.

Turn a failing test from *any* automation framework into an evidence-grounded
root-cause analysis, a confidence score, an owning team, and a tracker-ready bug
report — then render it to Markdown, JSON, HTML, or the console.

Architecture (strict, one-directional dependencies)::

    Adapters  ->  Core Domain  <-  AI Engine  ->  Reporting  ->  Output

* **Core domain** (:mod:`aiqa.core`) — pure, framework-agnostic models and
  interfaces. Depends on nothing but the standard library.
* **Adapters** (:mod:`aiqa.adapters`) — the only layer that knows a framework;
  each produces a :class:`FailureContext`.
* **AI engine** (:mod:`aiqa.analysis`) — accepts only a ``FailureContext`` and
  produces an :class:`AnalysisResult`. Never imports a framework.
* **Reporting** (:mod:`aiqa.reporting`) — renders an ``AnalysisResult`` only.

Quick start::

    from aiqa import FailureAnalyzer, FailureContext, render

    context = FailureContext.from_dict(payload)     # or use an adapter
    result = FailureAnalyzer().analyze(context)
    print(render(result, "markdown", context))
"""

from __future__ import annotations

from . import adapters
from .analysis import FailureAnalyzer, InMemoryIndex, NullIndex, OfflineProvider, OpenAIProvider
from .config import AiqaConfig, config
from .core import (
    AnalysisResult,
    BugReport,
    ConfidenceScore,
    ConsoleMessage,
    Evidence,
    ExceptionInfo,
    ExecutionContext,
    FailureCategory,
    FailureContext,
    FailureContextBuilder,
    FailureMetadata,
    LogEntry,
    NetworkEvent,
    Recommendation,
    RootCause,
    Severity,
    SimilarFailure,
)
from .core.interfaces import Analyzer, FrameworkAdapter, LLMProvider, Reporter, SimilarityIndex
from .reporting import BugReportBuilder, available_formats, get_reporter

__version__ = "2.0.1"

__all__ = [
    "__version__",
    # engine
    "FailureAnalyzer",
    "analyze",
    "render",
    # domain
    "FailureContext",
    "FailureContextBuilder",
    "AnalysisResult",
    "BugReport",
    "Evidence",
    "ExceptionInfo",
    "ExecutionContext",
    "FailureMetadata",
    "ConsoleMessage",
    "NetworkEvent",
    "LogEntry",
    "RootCause",
    "Recommendation",
    "ConfidenceScore",
    "SimilarFailure",
    "FailureCategory",
    "Severity",
    # interfaces (extension points)
    "Analyzer",
    "FrameworkAdapter",
    "Reporter",
    "LLMProvider",
    "SimilarityIndex",
    # analysis backends
    "OfflineProvider",
    "OpenAIProvider",
    "InMemoryIndex",
    "NullIndex",
    # reporting
    "BugReportBuilder",
    "available_formats",
    "get_reporter",
    # config + subpackages
    "AiqaConfig",
    "config",
    "adapters",
]


def analyze(context: FailureContext, **kwargs) -> AnalysisResult:
    """Convenience: analyze a :class:`FailureContext` with a default engine."""
    return FailureAnalyzer(**kwargs).analyze(context)


def render(result: AnalysisResult, format: str = "markdown",
           context: FailureContext | None = None) -> str:
    """Convenience: render an :class:`AnalysisResult` in the given format."""
    return get_reporter(format).render(result, context)
