"""Pluggable language-model providers for the analysis engine.

The engine depends only on the :class:`~aiqa.core.interfaces.LLMProvider`
protocol, never on a concrete SDK. Two providers ship by default:

* :class:`OfflineProvider` — always unavailable, forcing the deterministic
  heuristic path (the zero-dependency default).
* :class:`OpenAIProvider` — lazily imports the ``openai`` package only when
  actually used, so the SDK installs and runs without it.

Custom providers (Azure, Anthropic, Gemini, Ollama, a local model, ...) are
added by implementing the same three-member protocol and passing an instance to
:class:`~aiqa.analysis.analyzer.FailureAnalyzer` — no existing code changes.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


class OfflineProvider:
    """A no-op provider that is never available (pure heuristic mode)."""

    name = "offline"

    def available(self) -> bool:
        return False

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:  # pragma: no cover
        raise RuntimeError("OfflineProvider cannot complete prompts")


class OpenAIProvider:
    """OpenAI-compatible chat provider (lazy import, JSON-mode responses)."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("AIQA_API_KEY") or os.getenv("OPENAI_API_KEY")
        self._model = model or os.getenv("AIQA_MODEL", "gpt-4o-mini")
        self._base_url = base_url or os.getenv("AIQA_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        self._client: Any = None

    def available(self) -> bool:
        if not self._api_key:
            return False
        try:  # lazy: only import when a key is present
            import openai  # noqa: F401

            return True
        except Exception:
            return False

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "Respond with strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return _loads_lenient(content)


def _loads_lenient(text: str) -> dict[str, Any]:
    """Parse JSON, tolerating code fences or surrounding prose."""
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                pass
    return {}


def default_provider() -> Any:
    """Return an :class:`OpenAIProvider` if a key is configured, else offline."""
    provider = OpenAIProvider()
    return provider if provider.available() else OfflineProvider()
