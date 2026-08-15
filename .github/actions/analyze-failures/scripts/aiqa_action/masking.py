"""Secret masking for anything the action emits (logs, summary, PR comment).

Reuses the framework-agnostic :class:`aiqa.core.masking.SecretMasker` so there
is a single masking implementation across the SDK, CLI and this action. Only the
environment-seeding convenience (which is CI-specific) lives here.
"""

from __future__ import annotations

import os

from aiqa.core.masking import SecretMasker

__all__ = ["SecretMasker", "default_masker"]


def default_masker(*extra_secrets: str) -> SecretMasker:
    """A masker seeded from the environment's well-known secret variables."""
    seeds = [
        os.getenv("GITHUB_TOKEN", ""),
        os.getenv("INPUT_LLM_API_KEY", ""),
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("AIQA_API_KEY", ""),
        *extra_secrets,
    ]
    return SecretMasker(seeds)
