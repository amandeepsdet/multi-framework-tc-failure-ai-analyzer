"""Secret masking so evidence never leaks credentials into an LLM prompt.

The engine may send DOM, logs, network traffic, and API responses to a
third-party model. This module scrubs passwords, JWTs, bearer tokens, API keys,
cookies, and (optionally) URLs *before* anything is serialised or transmitted.

Masking is intentionally conservative and idempotent: running it twice yields
the same result, and it operates recursively over arbitrary JSON-like data.
"""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "***REDACTED***"

# Ordered list of (compiled pattern, replacement) applied to free text.
_TEXT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # JSON-style "password": "value"
    (re.compile(r'("?(?:password|passwd|pwd|secret|token|api[_-]?key)"?\s*[:=]\s*")([^"]*)(")', re.I),
     rf"\1{_REDACTED}\3"),
    # Authorization / X-Authorization headers (Bearer <jwt>)
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]+"), rf"\1 {_REDACTED}"),
    (re.compile(r"(?i)(x-authorization\s*[:=]\s*)\S+"), rf"\1{_REDACTED}"),
    # Raw JWTs (three base64url segments).
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), _REDACTED),
    # OpenAI-style keys and generic long secrets.
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), _REDACTED),
    (re.compile(r"(?i)(set-cookie\s*[:=]\s*)\S+"), rf"\1{_REDACTED}"),
]

# Mapping keys whose *values* are always redacted regardless of content.
_SENSITIVE_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "jwt", "jwt_token",
    "authorization", "x-authorization", "api_key", "apikey", "access_token",
    "refresh_token", "cookie", "set-cookie", "client_secret",
}

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def mask_text(text: str | None, *, mask_urls: bool = False) -> str:
    """Return ``text`` with secrets redacted; optionally redact URLs too."""
    if not text:
        return "" if text is None else text
    masked = text
    for pattern, replacement in _TEXT_PATTERNS:
        masked = pattern.sub(replacement, masked)
    if mask_urls:
        masked = _URL_PATTERN.sub(_REDACTED, masked)
    return masked


def mask_value(value: Any, *, mask_urls: bool = False) -> Any:
    """Recursively mask secrets inside dicts, lists, and strings."""
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.strip().lower() in _SENSITIVE_KEYS:
                result[key] = _REDACTED
            else:
                result[key] = mask_value(item, mask_urls=mask_urls)
        return result
    if isinstance(value, (list, tuple)):
        return [mask_value(item, mask_urls=mask_urls) for item in value]
    if isinstance(value, str):
        return mask_text(value, mask_urls=mask_urls)
    return value


def scrub(data: Any, *, enabled: bool = True, mask_urls: bool = False) -> Any:
    """Entry point used by the engine; a no-op when masking is disabled."""
    if not enabled:
        return data
    return mask_value(data, mask_urls=mask_urls)
