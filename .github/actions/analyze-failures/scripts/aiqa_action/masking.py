"""Secret masking for anything the action emits (logs, summary, PR comment).

The action treats test output as untrusted and never wants to leak the
``GITHUB_TOKEN`` or an LLM API key into a comment, summary, artifact, or log.
This is a best-effort redactor: it removes known secret *values* plus a few
common token *shapes*. It intentionally errs on the side of over-redacting.
"""

from __future__ import annotations

import re
from typing import Iterable

_REDACTION = "***"

# Common secret shapes (best-effort; order-independent).
_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),          # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),        # fine-grained PAT
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),              # OpenAI-style keys
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),       # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access key id
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),   # bearer headers
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}"),  # JWT
]


class SecretMasker:
    """Redacts explicit secret values and common token shapes from text."""

    def __init__(self, secrets: Iterable[str] | None = None) -> None:
        # Keep only non-trivial values to avoid redacting empty strings.
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
            out = out.replace(literal, _REDACTION)
        for pattern in _PATTERNS:
            out = pattern.sub(_REDACTION, out)
        return out


def default_masker(*extra_secrets: str) -> SecretMasker:
    """A masker seeded from the environment's well-known secret variables."""
    import os

    seeds = [
        os.getenv("GITHUB_TOKEN", ""),
        os.getenv("INPUT_LLM_API_KEY", ""),
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("AIQA_API_KEY", ""),
        *extra_secrets,
    ]
    return SecretMasker(seeds)
