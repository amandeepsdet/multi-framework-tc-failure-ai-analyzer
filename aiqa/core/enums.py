"""Framework-agnostic enumerations for the AIQA core domain.

These enums describe *failures* and *analysis*, never a specific application or
automation framework. They contain no DOM, product, or vendor terminology.
"""

from __future__ import annotations

from enum import Enum


class FailureCategory(str, Enum):
    """Canonical root-cause categories a failure may be classified into.

    Categories are intentionally generic so they apply to UI, API, mobile, and
    unit-level failures across any framework.
    """

    UI = "UI"
    FRONTEND = "Frontend"
    LOCATOR = "Locator"
    ELEMENT_NOT_FOUND = "Element Not Found"
    ELEMENT_NOT_VISIBLE = "Element Not Visible"
    API = "API"
    BACKEND = "Backend"
    AUTHENTICATION = "Authentication"
    AUTHORIZATION = "Authorization"
    SECURITY = "Security"
    NETWORK = "Network"
    TIMEOUT = "Timeout"
    PERFORMANCE = "Performance"
    INFRASTRUCTURE = "Infrastructure"
    DATABASE = "Database"
    DEPENDENCY = "Dependency"
    BROWSER = "Browser"
    MOBILE = "Mobile"
    ENVIRONMENT = "Environment"
    DATA = "Data"
    CONFIGURATION = "Configuration"
    ASSERTION = "Assertion"
    FLAKY = "Flaky"
    UNKNOWN = "Unknown"

    @classmethod
    def coerce(cls, value: str | FailureCategory | None) -> FailureCategory:
        """Best-effort coercion of arbitrary text to a known category."""
        if isinstance(value, cls):
            return value
        if not value:
            return cls.UNKNOWN
        needle = str(value).strip().lower()
        for member in cls:
            if member.value.lower() == needle or member.name.lower() == needle:
                return member
        keywords = {
            cls.AUTHENTICATION: ("auth", "login", "credential", "unauthenticated", "401"),
            cls.AUTHORIZATION: ("forbidden", "permission", "denied", "403"),
            cls.SECURITY: ("security", "csrf", "xss", "certificate", "ssl", "tls", "vulnerab"),
            cls.BACKEND: ("server error", "500", "backend", "upstream", "502", "503"),
            cls.DATABASE: (
                "database",
                "sql",
                "deadlock",
                "constraint",
                "no such table",
                "connection pool",
            ),
            cls.ELEMENT_NOT_FOUND: (
                "element not found",
                "no such element",
                "no node found",
                "unable to locate",
            ),
            cls.ELEMENT_NOT_VISIBLE: (
                "not visible",
                "not displayed",
                "not clickable",
                "not interactable",
            ),
            cls.LOCATOR: ("locator", "selector", "strict mode", "xpath", "css selector"),
            cls.TIMEOUT: ("timeout", "timed out", "deadline", "waiting for"),
            cls.NETWORK: ("network", "connection", "dns", "econnrefused", "unreachable"),
            cls.PERFORMANCE: ("slow", "latency", "performance", "too long"),
            cls.DEPENDENCY: (
                "modulenotfound",
                "importerror",
                "no module named",
                "dependency",
                "package",
            ),
            cls.MOBILE: ("appium", "android", "ios", "mobile", "device"),
            cls.FLAKY: ("flaky", "intermittent", "race condition"),
            cls.API: ("api", "endpoint", "rest", "request failed"),
            cls.ASSERTION: ("assert", "expected", "did not equal"),
            cls.FRONTEND: ("frontend", "javascript error", "react", "vue", "angular"),
            cls.UI: ("render", "displayed", "layout"),
        }
        for member, hints in keywords.items():
            if any(hint in needle for hint in hints):
                return member
        return cls.UNKNOWN


class Severity(str, Enum):
    """Business impact of a failure, independent of framework."""

    BLOCKER = "Blocker"
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    TRIVIAL = "Trivial"

    @classmethod
    def coerce(cls, value: str | Severity | None) -> Severity:
        if isinstance(value, cls):
            return value
        if not value:
            return cls.MAJOR
        needle = str(value).strip().lower()
        for member in cls:
            if member.value.lower() == needle or member.name.lower() == needle:
                return member
        return cls.MAJOR


class RiskLevel(str, Enum):
    """Release/impact risk associated with a classified failure."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

    @classmethod
    def coerce(cls, value: str | RiskLevel | None) -> RiskLevel:
        if isinstance(value, cls):
            return value
        if not value:
            return cls.MEDIUM
        needle = str(value).strip().lower()
        for member in cls:
            if member.value.lower() == needle or member.name.lower() == needle:
                return member
        return cls.MEDIUM
