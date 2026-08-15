"""Framework-agnostic secret masking utility.

A small, standard-library-only redactor for scrubbing secrets from any text the
tooling emits (logs, summaries, reports, CI comments). It removes known secret
*values* plus a few common token *shapes*, and errs on the side of
over-redacting. It has no framework or application knowledge, so it belongs in
the core and can be reused by the SDK, the CLI, and the GitHub Action alike.

The legacy :mod:`qa_ai_engine.security` module keeps its own richer, recursive
dict/key-aware masker used specifically for scrubbing LLM prompts; this utility
covers the generic free-text case shared across the codebase.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

REDACTION = "***"

# Common secret shapes (best-effort; order-independent).
_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),  # fine-grained PAT
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),  # OpenAI-style keys
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),  # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),  # bearer headers
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"),  # JWT
]


class SecretMasker:
    """Redacts explicit secret values and common token shapes from text."""

    def __init__(self, secrets: Iterable[str] | None = None) -> None:
        # Keep only non-trivial values to avoid redacting empty/short strings.
        self._literals = sorted(
            {s for s in (secrets or []) if s and len(s) >= 4},
            key=len,
            reverse=True,
        )

    def mask(self, text: str | None) -> str:
        if not text:
            return "" if text is None else text
        out = text
        for literal in self._literals:
            out = out.replace(literal, REDACTION)
        for pattern in _PATTERNS:
            out = pattern.sub(REDACTION, out)
        return out


def mask_secrets(text: str | None, *secrets: str) -> str:
    """Convenience: mask ``text`` given zero or more explicit secret values."""
    return SecretMasker(secrets).mask(text)
