"""Provider-agnostic LLM client abstraction.

The engine depends only on :class:`BaseLLMClient`; concrete providers (OpenAI,
Azure OpenAI, Anthropic Claude, Google Gemini, local Ollama) are thin adapters
whose SDKs are imported lazily so the framework installs and runs with none of
them present. When no provider is configured the :class:`HeuristicLLMClient`
reports itself unavailable, and the analyzer transparently falls back to its
deterministic rule engine.

Design goals: dependency injection, open/closed extensibility (add a provider
by subclassing), and no tight coupling to any single vendor.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config

logger = get_logger("ai.llm_client")


class LLMUnavailableError(RuntimeError):
    """Raised when a provider is requested but its SDK/credentials are missing."""


class BaseLLMClient(ABC):
    """Abstract chat-completion client.

    Concrete clients implement :meth:`_complete`. Callers use :meth:`complete`
    (text) and, optionally, :meth:`complete_vision` (text + image).
    """

    name: str = "base"

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the client can actually service a request."""

    @abstractmethod
    def _complete(self, prompt: str, system: str | None) -> str:
        """Provider-specific completion call."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Return the model's text completion for ``prompt``."""
        if not self.is_available():
            raise LLMUnavailableError(f"LLM provider '{self.name}' is not available")
        logger.info("LLM completion via %s (model=%s)", self.name, self.cfg.model)
        return self._complete(prompt, system)

    def complete_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        """Complete and parse the response as JSON (robust to code fences)."""
        raw = self.complete(prompt, system)
        return extract_json(raw)

    def supports_vision(self) -> bool:
        return False

    def complete_vision(self, prompt: str, image_path: str, system: str | None = None) -> str:
        raise NotImplementedError(f"{self.name} does not support vision")


# --------------------------------------------------------------------------- #
# Offline / default client
# --------------------------------------------------------------------------- #
class HeuristicLLMClient(BaseLLMClient):
    """A no-op client that signals "use the deterministic engine instead"."""

    name = "heuristic"

    def is_available(self) -> bool:
        return False

    def _complete(self, prompt: str, system: str | None) -> str:  # pragma: no cover
        raise LLMUnavailableError("Heuristic client performs no LLM calls")


# --------------------------------------------------------------------------- #
# Cloud + local providers (SDKs imported lazily)
# --------------------------------------------------------------------------- #
class OpenAIClient(BaseLLMClient):
    """OpenAI Chat Completions client (also supports vision)."""

    name = "openai"

    def _key(self) -> str:
        import os

        return self.cfg.api_key or os.getenv("OPENAI_API_KEY", "")

    def is_available(self) -> bool:
        try:
            import openai  # noqa: F401
        except Exception:
            return False
        return bool(self._key())

    def _client(self):  # type: ignore[no-untyped-def]
        import openai

        kwargs: dict[str, Any] = {"api_key": self._key()}
        if self.cfg.base_url:
            kwargs["base_url"] = self.cfg.base_url
        return openai.OpenAI(**kwargs)

    def _complete(self, prompt: str, system: str | None) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        resp = self._client().chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            timeout=self.cfg.request_timeout,
        )
        return resp.choices[0].message.content or ""

    def supports_vision(self) -> bool:
        return self.cfg.vision_enabled

    def complete_vision(self, prompt: str, image_path: str, system: str | None = None) -> str:
        import base64

        with open(image_path, "rb") as handle:
            b64 = base64.b64encode(handle.read()).decode("ascii")
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": content}
        ]
        resp = self._client().chat.completions.create(
            model=self.cfg.vision_model,
            messages=messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content or ""


class AzureOpenAIClient(OpenAIClient):
    """Azure OpenAI variant (deployment-based routing)."""

    name = "azure"

    def _key(self) -> str:
        import os

        return self.cfg.api_key or os.getenv("AZURE_OPENAI_API_KEY", "")

    def is_available(self) -> bool:
        try:
            import openai  # noqa: F401
        except Exception:
            return False
        return bool(self._key() and self.cfg.azure_endpoint and self.cfg.azure_deployment)

    def _client(self):  # type: ignore[no-untyped-def]
        import openai

        return openai.AzureOpenAI(
            api_key=self._key(),
            azure_endpoint=self.cfg.azure_endpoint,
            api_version=self.cfg.azure_api_version,
        )

    def _complete(self, prompt: str, system: str | None) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        resp = self._client().chat.completions.create(
            model=self.cfg.azure_deployment,
            messages=messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content or ""


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude client."""

    name = "claude"

    def _key(self) -> str:
        import os

        return self.cfg.api_key or os.getenv("ANTHROPIC_API_KEY", "")

    def is_available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return bool(self._key())

    def _complete(self, prompt: str, system: str | None) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self._key())
        resp = client.messages.create(
            model=self.cfg.model,
            system=system or "",
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


class GeminiClient(BaseLLMClient):
    """Google Gemini client."""

    name = "gemini"

    def _key(self) -> str:
        import os

        return self.cfg.api_key or os.getenv("GOOGLE_API_KEY", "")

    def is_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401
        except Exception:
            return False
        return bool(self._key())

    def _complete(self, prompt: str, system: str | None) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self._key())
        model = genai.GenerativeModel(self.cfg.model, system_instruction=system or None)
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": self.cfg.temperature,
                "max_output_tokens": self.cfg.max_tokens,
            },
        )
        return resp.text or ""


class OllamaClient(BaseLLMClient):
    """Local Ollama client (llama3, mistral, deepseek, ...) — no API key."""

    name = "ollama"

    def is_available(self) -> bool:
        try:
            import requests

            requests.get(f"{self.cfg.ollama_host}/api/tags", timeout=2)
            return True
        except Exception:
            return False

    def _complete(self, prompt: str, system: str | None) -> str:
        import requests

        resp = requests.post(
            f"{self.cfg.ollama_host}/api/generate",
            json={
                "model": self.cfg.model,
                "prompt": prompt,
                "system": system or "",
                "stream": False,
                "options": {"temperature": self.cfg.temperature},
            },
            timeout=self.cfg.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


_PROVIDERS: dict[str, type[BaseLLMClient]] = {
    "heuristic": HeuristicLLMClient,
    "none": HeuristicLLMClient,
    "offline": HeuristicLLMClient,
    "openai": OpenAIClient,
    "azure": AzureOpenAIClient,
    "azure_openai": AzureOpenAIClient,
    "claude": ClaudeClient,
    "anthropic": ClaudeClient,
    "gemini": GeminiClient,
    "google": GeminiClient,
    "ollama": OllamaClient,
}


def get_llm_client(cfg: AIConfig = ai_config) -> BaseLLMClient:
    """Factory: build the configured client, defaulting to heuristic.

    Never raises for an unknown provider — it degrades gracefully to the
    offline heuristic client so a misconfiguration cannot break a test run.
    """
    provider = (cfg.provider or "heuristic").lower()
    client_cls = _PROVIDERS.get(provider)
    if client_cls is None:
        logger.warning("Unknown AI provider '%s'; falling back to heuristic", provider)
        client_cls = HeuristicLLMClient
    return client_cls(cfg)


def register_provider(name: str, client_cls: type[BaseLLMClient]) -> None:
    """Register a custom provider (open/closed extensibility)."""
    _PROVIDERS[name.lower()] = client_cls


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response, tolerating code fences/prose."""
    if not text:
        return {}
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        # Drop an optional language tag on the first line.
        if "\n" in candidate:
            first, rest = candidate.split("\n", 1)
            if first.strip().lower() in {"json", ""}:
                candidate = rest
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return {}
