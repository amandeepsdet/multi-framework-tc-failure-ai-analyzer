"""AIQA analysis engine — turns a FailureContext into an AnalysisResult.

Depends only on the core domain (plus lazily-imported optional LLM SDKs). It
never imports an automation framework or application code.
"""

from __future__ import annotations

from .analyzer import FailureAnalyzer
from .heuristics import HeuristicClassifier, HeuristicVerdict, severity_for
from .llm import OfflineProvider, OpenAIProvider, default_provider
from .owners import DEFAULT_OWNERS, owner_for
from .rag import InMemoryIndex, NullIndex

__all__ = [
    "FailureAnalyzer",
    "HeuristicClassifier",
    "HeuristicVerdict",
    "severity_for",
    "OfflineProvider",
    "OpenAIProvider",
    "default_provider",
    "DEFAULT_OWNERS",
    "owner_for",
    "InMemoryIndex",
    "NullIndex",
]
