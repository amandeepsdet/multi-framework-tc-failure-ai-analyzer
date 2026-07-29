"""Abstract interfaces (ports) for the AIQA SDK.

These abstractions are the seams that keep the architecture decoupled and make
every component independently testable and replaceable (Dependency Inversion):

* :class:`FrameworkAdapter` — turns framework-specific state into a
  :class:`~aiqa.core.models.FailureContext`.
* :class:`Analyzer` — turns a ``FailureContext`` into an
  :class:`~aiqa.core.models.AnalysisResult`.
* :class:`Reporter` — renders an ``AnalysisResult`` into an output format.
* :class:`LLMProvider` — a pluggable language-model backend.
* :class:`SimilarityIndex` — a pluggable RAG / history backend.

Depending on this module never pulls in a framework: it imports only the core
domain models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from .models import AnalysisResult, FailureContext


class FrameworkAdapter(ABC):
    """Converts framework-specific failure state into a generic context.

    Concrete adapters (Playwright, Selenium, pytest, Robot Framework, ...) live
    in :mod:`aiqa.adapters`. The core and the engine never import them.
    """

    #: Short, stable identifier for the source framework (e.g. ``"playwright"``).
    name: str = "generic"

    @abstractmethod
    def collect_failure_context(self, *args: Any, **kwargs: Any) -> FailureContext:
        """Collect all available evidence and return a :class:`FailureContext`."""
        raise NotImplementedError


class Analyzer(ABC):
    """Produces an :class:`AnalysisResult` from a :class:`FailureContext`."""

    @abstractmethod
    def analyze(self, context: FailureContext) -> AnalysisResult:
        raise NotImplementedError


class Reporter(ABC):
    """Renders an :class:`AnalysisResult` (optionally with its context)."""

    #: Output format key, e.g. ``"markdown"``, ``"json"``, ``"html"``.
    format: str = "text"

    @abstractmethod
    def render(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        raise NotImplementedError


@runtime_checkable
class LLMProvider(Protocol):
    """A pluggable language-model backend.

    Implementations may call a cloud API or a local model. They must degrade
    gracefully: when unavailable, :meth:`available` returns ``False`` and the
    engine transparently falls back to the deterministic heuristic analyzer.
    """

    name: str

    def available(self) -> bool: ...

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]: ...


@runtime_checkable
class SimilarityIndex(Protocol):
    """A pluggable similarity/RAG backend over past failures."""

    def add(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None: ...

    def search(self, text: str, top_k: int) -> list[dict[str, Any]]: ...
