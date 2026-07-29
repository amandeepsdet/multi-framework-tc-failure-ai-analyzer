"""Central configuration for the ThingsBoard automation framework.

All environment-specific and tunable values live here so that tests and page
objects never hardcode URLs, credentials, or timing values. Secrets (password,
JWT token) are loaded from a gitignored ``.env`` file via python-dotenv, so
they never live in source control. Every value can still be overridden with a
real environment variable, which is the recommended approach in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load secrets from a local .env at the project root (if present). Real
# environment variables always take precedence over .env values.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env(key: str, default: str) -> str:
    """Return an environment variable value, falling back to a default."""
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    """Return an integer environment variable value, falling back to a default."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Immutable configuration object shared across the framework."""

    # --- Application under test -------------------------------------------
    # The account lives on ThingsBoard Cloud (token issuer: thingsboard.cloud),
    # not the public demo server. Override via env vars for other environments.
    base_url: str = _env("TB_BASE_URL", "https://thingsboard.cloud")
    username: str = _env("TB_USERNAME", "amandeep242712@gmail.com")

    # --- Secrets (sourced from .env / environment, never hardcoded) -------
    password: str = _env("TB_PASSWORD", "")
    # Optional pre-issued JWT used by token-based negative tests / manual runs.
    jwt_token: str = _env("TB_JWT_TOKEN", "")

    # --- Target dashboard --------------------------------------------------
    dashboard_name: str = _env("TB_DASHBOARD_NAME", "Fuel Level Monitoring")

    # --- Timing / waits (milliseconds unless noted) ------------------------
    default_timeout_ms: int = _env_int("TB_TIMEOUT_MS", 30_000)
    poll_retries: int = _env_int("TB_POLL_RETRIES", 3)
    poll_interval_seconds: int = _env_int("TB_POLL_INTERVAL", 5)
    api_retries: int = _env_int("TB_API_RETRIES", 3)

    # --- Telemetry validation ranges --------------------------------------
    # (min, max) inclusive bounds used by range assertions.
    fuel_level_range: tuple[float, float] = field(default=(0.0, 100.0))
    temperature_range: tuple[float, float] = field(default=(-40.0, 100.0))
    battery_range: tuple[float, float] = field(default=(0.0, 100.0))
    valid_connection_states: tuple[str, ...] = field(default=("online", "offline", "active", "inactive"))

    @property
    def login_endpoint(self) -> str:
        return f"{self.base_url}/api/auth/login"

    @property
    def devices_endpoint(self) -> str:
        return f"{self.base_url}/api/tenant/devices"

    def telemetry_endpoint(self, device_id: str) -> str:
        return f"{self.base_url}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"


# Single shared instance imported throughout the framework.
config = Config()
