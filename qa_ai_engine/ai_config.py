"""Configuration for the AI Failure Analysis Engine.

Every AI capability is configuration-driven and defaults to a fully offline,
zero-dependency, zero-secret mode so the framework keeps working on a fresh
setup with no API keys installed. Cloud providers and heavy vector databases
are opt-in via environment variables.

All values are read from the environment (loaded from the project ``.env`` by
``utils.config``) so nothing has to be hardcoded and CI can override anything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Importing utils.config triggers python-dotenv to load the project .env once,
# so AI_* variables placed in .env are available here too.
try:  # pragma: no cover - defensive: AI package must import even standalone
    from utils.config import config as _framework_config  # noqa: F401
except Exception:  # pragma: no cover
    _framework_config = None  # type: ignore[assignment]


def _base_dir() -> Path:
    """Return the directory under which AI artifacts are created.

    When embedded in the host framework this is the project root (the current
    working directory when pytest runs). When installed as a standalone library
    in another Playwright project, artifacts still land in *that* project's
    working directory rather than inside site-packages. ``AI_BASE_DIR`` overrides.
    """
    override = os.getenv("AI_BASE_DIR")
    return Path(override).resolve() if override else Path.cwd()


_PROJECT_ROOT = _base_dir()


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _resolve_dir(key: str, default_name: str) -> Path:
    raw = os.getenv(key)
    path = Path(raw) if raw else _PROJECT_ROOT / default_name
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path


@dataclass(frozen=True)
class AIConfig:
    """Immutable, environment-driven configuration for the AI engine.

    The defaults describe a self-contained "offline" engine:

    * ``provider = "heuristic"`` — deterministic rule-based analysis, no network.
    * ``embedding_provider = "hash"`` — pure-Python hashing embeddings.
    * ``vector_backend = "json"`` — a local JSON similarity index.

    Switching ``AI_PROVIDER`` to ``openai``/``azure``/``claude``/``gemini``/
    ``ollama`` upgrades analysis to a real LLM without touching any call site.
    """

    # --- Master switches ---------------------------------------------------
    enabled: bool = _env_bool("AI_ENABLED", False)
    analyze_on_failure: bool = _env_bool("AI_ANALYZE_ON_FAILURE", True)
    collect_evidence: bool = _env_bool("AI_COLLECT_EVIDENCE", True)

    # --- LLM provider ------------------------------------------------------
    provider: str = _env("AI_PROVIDER", "heuristic").lower()
    model: str = _env("AI_MODEL", "gpt-4o-mini")
    temperature: float = _env_float("AI_TEMPERATURE", 0.1)
    max_tokens: int = _env_int("AI_MAX_TOKENS", 1200)
    request_timeout: int = _env_int("AI_REQUEST_TIMEOUT", 60)

    # Generic key (each provider also honours its own conventional env var).
    api_key: str = _env("AI_API_KEY", "")
    base_url: str = _env("AI_BASE_URL", "")

    # Azure OpenAI specifics.
    azure_endpoint: str = _env("AZURE_OPENAI_ENDPOINT", "")
    azure_api_version: str = _env("AZURE_OPENAI_API_VERSION", "2024-06-01")
    azure_deployment: str = _env("AZURE_OPENAI_DEPLOYMENT", "")

    # Ollama specifics (local models: llama3, mistral, deepseek, ...).
    ollama_host: str = _env("OLLAMA_HOST", "http://localhost:11434")

    # --- Vision ------------------------------------------------------------
    vision_enabled: bool = _env_bool("AI_VISION_ENABLED", False)
    vision_model: str = _env("AI_VISION_MODEL", "gpt-4o-mini")

    # --- Embeddings + vector store ----------------------------------------
    embedding_provider: str = _env("AI_EMBEDDING_PROVIDER", "hash").lower()
    embedding_model: str = _env("AI_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dim: int = _env_int("AI_EMBEDDING_DIM", 256)
    vector_backend: str = _env("AI_VECTOR_BACKEND", "json").lower()
    rag_top_k: int = _env_int("AI_RAG_TOP_K", 5)

    # --- Security ----------------------------------------------------------
    mask_secrets: bool = _env_bool("AI_MASK_SECRETS", True)
    mask_urls: bool = _env_bool("AI_MASK_URLS", False)
    dom_max_chars: int = _env_int("AI_DOM_MAX_CHARS", 20_000)

    # --- Paths -------------------------------------------------------------
    prompts_dir: Path = field(default_factory=lambda: _resolve_dir("AI_PROMPTS_DIR", "prompts"))
    history_dir: Path = field(default_factory=lambda: _resolve_dir("AI_HISTORY_DIR", "failure_history"))
    reports_dir: Path = field(default_factory=lambda: _resolve_dir("AI_REPORTS_DIR", "ai_reports"))
    vector_dir: Path = field(default_factory=lambda: _resolve_dir("AI_VECTOR_DIR", "vector_db"))
    # Destination for the single consolidated AI dashboard produced once per run.
    dashboard_dir: Path = field(default_factory=lambda: _resolve_dir("AI_DASHBOARD_DIR", "reports"))

    framework_version: str = _env("FRAMEWORK_VERSION", "1.0.0")

    def ensure_dirs(self) -> None:
        """Create all output directories if they do not yet exist."""
        for path in (self.prompts_dir, self.history_dir, self.reports_dir, self.vector_dir, self.dashboard_dir):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def uses_llm(self) -> bool:
        """True when a real (non-heuristic) LLM provider is configured."""
        return self.provider not in {"heuristic", "none", "offline", ""}


# Single shared instance imported throughout the AI package.
ai_config = AIConfig()
