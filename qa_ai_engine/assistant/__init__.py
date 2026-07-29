"""Interactive AI-powered QA Assistant service package.

Exposes reusable services (:class:`QAAssistant`, :class:`ChatEngine`,
:class:`ToolRegistry`) that back the CLI (``qa_ai.py``), the interactive chat,
and a potential future MCP server. Business logic is intentionally decoupled
from any terminal/front-end concern.
"""

from __future__ import annotations

from .assistant import QAAssistant
from .chat_engine import ChatEngine
from .tool_registry import BaseTool, ToolRegistry

__all__ = ["QAAssistant", "ChatEngine", "ToolRegistry", "BaseTool"]
