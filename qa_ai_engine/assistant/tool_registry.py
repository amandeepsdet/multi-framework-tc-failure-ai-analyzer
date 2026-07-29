"""Modular tool registry for the QA AI Assistant.

Each assistant capability is a self-describing :class:`BaseTool` exposing
``execute()``, ``description()`` and ``examples()``. Tools are thin wrappers
around the :class:`~ai.engine.AIEngine` services, so the same registry can back
the CLI, the interactive chat, and (later) an MCP server without change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from qa_ai_engine._logging import get_logger

logger = get_logger("assistant.tools")


class BaseTool(ABC):
    """A single, self-describing assistant capability."""

    name: str = "tool"

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Run the tool and return a serialisable result."""

    @abstractmethod
    def description(self) -> str:
        """One-line description of what the tool does."""

    def examples(self) -> list[str]:
        """Return example natural-language invocations."""
        return []


class _FnTool(BaseTool):
    """Adapter turning a bound method into a tool (keeps wiring concise)."""

    def __init__(self, name: str, fn: Callable[..., Any], description: str, examples: list[str]) -> None:
        self.name = name
        self._fn = fn
        self._description = description
        self._examples = examples

    def execute(self, **kwargs: Any) -> Any:
        return self._fn(**kwargs)

    def description(self) -> str:
        return self._description

    def examples(self) -> list[str]:
        return self._examples


class ToolRegistry:
    """Holds and dispatches the assistant's tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def register_fn(
        self, name: str, fn: Callable[..., Any], description: str, examples: list[str] | None = None
    ) -> None:
        self.register(_FnTool(name, fn, description, examples or []))

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def execute(self, name: str, **kwargs: Any) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        logger.info("Executing tool '%s'", name)
        return tool.execute(**kwargs)

    def describe_all(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description(), "examples": t.examples()}
            for t in self.all()
        ]
