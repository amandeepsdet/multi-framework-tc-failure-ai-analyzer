"""Category-to-owner routing.

A small, configurable mapping from a :class:`FailureCategory` to the team most
likely to own the fix. This is deliberately generic (no product teams) and can
be overridden per project by passing a custom mapping to the analyzer.
"""

from __future__ import annotations

from ..core.enums import FailureCategory

DEFAULT_OWNERS: dict[FailureCategory, str] = {
    FailureCategory.BACKEND: "Backend / Platform team",
    FailureCategory.API: "Backend / API team",
    FailureCategory.AUTHENTICATION: "Identity / Auth team",
    FailureCategory.AUTHORIZATION: "Identity / Auth team",
    FailureCategory.SECURITY: "Security team",
    FailureCategory.LOCATOR: "UI Automation / QA team",
    FailureCategory.ELEMENT_NOT_FOUND: "UI Automation / QA team",
    FailureCategory.ELEMENT_NOT_VISIBLE: "UI Automation / QA team",
    FailureCategory.UI: "Frontend team",
    FailureCategory.FRONTEND: "Frontend team",
    FailureCategory.NETWORK: "Infrastructure / SRE team",
    FailureCategory.TIMEOUT: "Performance / SRE team",
    FailureCategory.PERFORMANCE: "Performance / SRE team",
    FailureCategory.INFRASTRUCTURE: "Infrastructure / SRE team",
    FailureCategory.DATABASE: "Database team",
    FailureCategory.DEPENDENCY: "DevOps / Build team",
    FailureCategory.BROWSER: "UI Automation / QA team",
    FailureCategory.MOBILE: "Mobile / QA team",
    FailureCategory.ENVIRONMENT: "DevOps / Environment owners",
    FailureCategory.DATA: "Test-data owners",
    FailureCategory.CONFIGURATION: "QA Framework owners",
    FailureCategory.ASSERTION: "Test authors / QA team",
    FailureCategory.FLAKY: "QA Automation team",
    FailureCategory.UNKNOWN: "Triage / QA lead",
}


def owner_for(
    category: FailureCategory, overrides: dict[FailureCategory, str] | None = None
) -> str:
    table = {**DEFAULT_OWNERS, **(overrides or {})}
    return table.get(category, table[FailureCategory.UNKNOWN])


class OwnerResolver:
    """Resolves the owning team for a failure category (with custom mapping).

    A thin, testable component over :func:`owner_for` so projects can inject and
    extend their own routing without touching the analyzer.
    """

    def __init__(self, overrides: dict[FailureCategory, str] | None = None) -> None:
        self._overrides = dict(overrides or {})

    def register(self, category: FailureCategory, owner: str) -> OwnerResolver:
        self._overrides[category] = owner
        return self

    def resolve(self, category: FailureCategory) -> str:
        return owner_for(category, self._overrides)
