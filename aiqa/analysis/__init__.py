"""AIQA analysis engine — turns a FailureContext into an AnalysisResult.

Depends only on the core domain (plus lazily-imported optional LLM SDKs). It
never imports an automation framework or application code.
"""

from __future__ import annotations

from .analyzer import FailureAnalyzer
from .classifier import Classification, FailureClassifier
from .heuristics import HeuristicClassifier, HeuristicVerdict, risk_for, severity_for
from .llm import OfflineProvider, OpenAIProvider, default_provider
from .owners import DEFAULT_OWNERS, OwnerResolver, owner_for
from .rag import InMemoryIndex, NullIndex
from .reasoning import ConfidenceReasoningBuilder

__all__ = [
    "FailureAnalyzer",
    "FailureClassifier",
    "Classification",
    "ConfidenceReasoningBuilder",
    "HeuristicClassifier",
    "HeuristicVerdict",
    "severity_for",
    "risk_for",
    "OfflineProvider",
    "OpenAIProvider",
    "default_provider",
    "DEFAULT_OWNERS",
    "OwnerResolver",
    "owner_for",
    "InMemoryIndex",
    "NullIndex",
]
