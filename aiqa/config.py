"""AIQA SDK configuration (generic, environment-driven).

All settings are optional and framework-agnostic. The SDK works with zero
configuration (offline heuristic mode). Environment variables let you enable an
LLM provider and persistence without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class AiqaConfig:
    """Runtime configuration for the SDK, populated from the environment."""

    provider: str = field(default_factory=lambda: os.getenv("AIQA_PROVIDER", "offline"))
    model: str = field(default_factory=lambda: os.getenv("AIQA_MODEL", "gpt-4o-mini"))
    api_key: str | None = field(default_factory=lambda: os.getenv("AIQA_API_KEY") or os.getenv("OPENAI_API_KEY"))
    base_url: str | None = field(default_factory=lambda: os.getenv("AIQA_BASE_URL"))
    base_dir: Path = field(default_factory=lambda: Path(os.getenv("AIQA_BASE_DIR", ".aiqa")))
    enable_history: bool = field(default_factory=lambda: _flag("AIQA_ENABLE_HISTORY", False))
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("AIQA_RAG_TOP_K", "3")))

    @property
    def history_path(self) -> Path:
        return self.base_dir / "history.json"

    @property
    def uses_llm(self) -> bool:
        return self.provider.lower() not in ("offline", "heuristic", "none", "")


#: Import-time singleton; construct your own AiqaConfig() to override.
config = AiqaConfig()
