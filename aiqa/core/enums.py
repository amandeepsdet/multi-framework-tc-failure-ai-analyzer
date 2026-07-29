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
    LOCATOR = "Locator"
    API = "API"
    BACKEND = "Backend"
    AUTHENTICATION = "Authentication"
    AUTHORIZATION = "Authorization"
    NETWORK = "Network"
    PERFORMANCE = "Performance"
    INFRASTRUCTURE = "Infrastructure"
    BROWSER = "Browser"
    ENVIRONMENT = "Environment"
    DATA = "Data"
    CONFIGURATION = "Configuration"
    ASSERTION = "Assertion"
    FLAKY = "Flaky"
    UNKNOWN = "Unknown"

    @classmethod
    def coerce(cls, value: "str | FailureCategory | None") -> "FailureCategory":
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
            cls.BACKEND: ("server error", "500", "backend", "database", "upstream"),
            cls.LOCATOR: ("locator", "selector", "element not found", "no such element"),
            cls.NETWORK: ("network", "connection", "dns", "econnrefused", "unreachable"),
            cls.PERFORMANCE: ("timeout", "timed out", "slow", "latency", "deadline"),
            cls.FLAKY: ("flaky", "intermittent", "race condition"),
            cls.API: ("api", "endpoint", "rest", "request failed"),
            cls.ASSERTION: ("assert", "expected", "did not equal"),
            cls.UI: ("render", "not visible", "not displayed"),
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
    def coerce(cls, value: "str | Severity | None") -> "Severity":
        if isinstance(value, cls):
            return value
        if not value:
            return cls.MAJOR
        needle = str(value).strip().lower()
        for member in cls:
            if member.value.lower() == needle or member.name.lower() == needle:
                return member
        return cls.MAJOR
