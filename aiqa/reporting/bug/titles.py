"""Natural-language bug-title generation.

Produces a concise, professional, human-sounding title from the analysis —
never a repetitive template like "Test X failed". The wording adapts to the
failure category and subcategory.
"""

from __future__ import annotations

from ...core.enums import FailureCategory
from ...core.models import AnalysisResult, FailureContext

_HTTP_TEMPLATES = {
    FailureCategory.BACKEND: "{code} returned by backend service during {scope}",
    FailureCategory.API: "{code} returned from API during {scope}",
}


def _scope(context: FailureContext | None) -> str:
    if context is None:
        return "the automated test"
    name = context.test_name
    # Use the specific test node (after '::') and humanise it.
    node = name.split("::")[-1]
    node = node.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    for suffix in (".py", ".robot", ".js", ".ts"):
        if node.endswith(suffix):
            node = node[: -len(suffix)]
    node = node.removeprefix("test_").replace("_", " ").strip()
    return node or "the automated test"


def _http_code(context: FailureContext | None) -> str:
    if context is None:
        return "An HTTP error"
    codes = sorted({n.status for n in context.evidence.network if n.status and n.status >= 400})
    return f"HTTP {codes[0]}" if codes else "An HTTP error"


def bug_title(result: AnalysisResult, context: FailureContext | None = None) -> str:
    cat = result.category
    sub = result.root_cause.subcategory
    scope = _scope(context)

    if cat is FailureCategory.AUTHENTICATION:
        return f"Authentication failed due to {sub.lower() or 'invalid credentials'}"
    if cat is FailureCategory.AUTHORIZATION:
        return f"Authorization denied — {sub.lower() or 'insufficient permissions'} during {scope}"
    if cat in (FailureCategory.BACKEND, FailureCategory.API):
        return f"{_http_code(context)} returned during {scope}"
    if cat in (
        FailureCategory.LOCATOR,
        FailureCategory.ELEMENT_NOT_FOUND,
        FailureCategory.ELEMENT_NOT_VISIBLE,
    ):
        return f"UI locator became stale after DOM update during {scope}"
    if cat in (FailureCategory.TIMEOUT, FailureCategory.PERFORMANCE):
        return f"Navigation timeout exceeded during {scope}"
    if cat is FailureCategory.NETWORK:
        return f"Network connection failed during {scope}"
    if cat is FailureCategory.ASSERTION:
        return f"Assertion mismatch detected during {scope}"
    if cat is FailureCategory.SECURITY:
        return f"Security check failed during {scope}"
    if cat is FailureCategory.DATABASE:
        return f"Database error encountered during {scope}"
    if cat is FailureCategory.DEPENDENCY:
        return f"Missing or broken dependency during {scope}"
    if cat is FailureCategory.UNKNOWN:
        return f"Unclassified failure during {scope}"
    return f"{cat.value} failure during {scope}"
