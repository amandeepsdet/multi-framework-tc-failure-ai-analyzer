"""AIQA core domain — pure, framework-agnostic building blocks.

This package contains the domain models, abstract interfaces, and the failure
context builder. It has **no** dependency on any automation framework or
application, and sits at the bottom of the dependency graph.
"""

from __future__ import annotations

from .context_builder import FailureContextBuilder
from .enums import FailureCategory, RiskLevel, Severity
from .interfaces import Analyzer, FrameworkAdapter, LLMProvider, Reporter, SimilarityIndex
from .models import (
    AnalysisResult,
    BugReport,
    ConfidenceReasoning,
    ConfidenceScore,
    ConsoleMessage,
    Evidence,
    ExceptionInfo,
    ExecutionContext,
    FailureContext,
    FailureMetadata,
    LogEntry,
    NetworkEvent,
    Recommendation,
    RootCause,
    SimilarFailure,
)

__all__ = [
    "FailureContextBuilder",
    "FailureCategory",
    "RiskLevel",
    "Severity",
    "Analyzer",
    "FrameworkAdapter",
    "LLMProvider",
    "Reporter",
    "SimilarityIndex",
    "AnalysisResult",
    "BugReport",
    "ConfidenceReasoning",
    "ConfidenceScore",
    "ConsoleMessage",
    "Evidence",
    "ExceptionInfo",
    "ExecutionContext",
    "FailureContext",
    "FailureMetadata",
    "LogEntry",
    "NetworkEvent",
    "Recommendation",
    "RootCause",
    "SimilarFailure",
]
