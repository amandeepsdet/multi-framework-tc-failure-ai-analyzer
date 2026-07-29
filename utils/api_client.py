"""Reusable ThingsBoard REST API client.

Wraps the subset of the ThingsBoard API needed by the framework:
authentication, device discovery, and telemetry retrieval. All HTTP concerns
(headers, JWT handling, retries, logging) are centralised here so tests stay
declarative and free of duplication.
"""

from __future__ import annotations

from typing import Any

import requests

from utils.config import Config, config
from utils.helpers import poll_until
from utils.logger import get_logger

logger = get_logger("utils.api_client")


class ThingsBoardAPIError(RuntimeError):
    """Raised when an API call returns an unexpected status code."""


class ThingsBoardAPIClient:
    """Thin, reusable wrapper around the ThingsBoard REST API."""

    def __init__(self, cfg: Config = config) -> None:
        self._config = cfg
        self._session = requests.Session()
        self._token: str | None = None

    # ------------------------------------------------------------------ auth
    def login(self) -> str:
        """Authenticate and cache the JWT token for subsequent requests.

        POST /api/auth/login
        """
        return self.login_with(self._config.username, self._config.password)

    def login_with(self, username: str, password: str) -> str:
        """Authenticate with explicit credentials (used by negative tests)."""
        logger.info("API login as %s", username)
        response = self._session.post(
            self._config.login_endpoint,
            json={"username": username, "password": password},
            timeout=self._config.default_timeout_ms / 1000,
        )
        if response.status_code != 200:
            raise ThingsBoardAPIError(
                f"Login failed: {response.status_code} {response.text[:200]}"
            )
        self._token = response.json()["token"]
        self._session.headers.update({"X-Authorization": f"Bearer {self._token}"})
        logger.info("API login successful; JWT acquired")
        return self._token

    def use_token(self, token: str) -> None:
        """Attach a pre-issued JWT token to the session (no login round-trip).

        Enables token-based scenarios such as expired/invalid-token negative
        tests and manual runs where a token is provided out of band.
        """
        self._token = token
        self._session.headers.update({"X-Authorization": f"Bearer {token}"})
        logger.info("Using externally supplied JWT token")

    @property
    def token(self) -> str | None:
        return self._token

    def _require_token(self) -> None:
        if not self._token:
            raise ThingsBoardAPIError("No JWT token; call login() first")

    # --------------------------------------------------------------- devices
    def get_devices(self, page_size: int = 100) -> list[dict[str, Any]]:
        """Return device records for the tenant.

        GET /api/tenant/devices
        """
        self._require_token()
        logger.info("Fetching device list")
        response = self._session.get(
            self._config.devices_endpoint,
            params={"pageSize": page_size, "page": 0},
            timeout=self._config.default_timeout_ms / 1000,
        )
        if response.status_code != 200:
            raise ThingsBoardAPIError(
                f"Get devices failed: {response.status_code} {response.text[:200]}"
            )
        devices = response.json().get("data", [])
        logger.info("Retrieved %d device(s)", len(devices))
        return devices

    def get_first_device_id(self) -> str:
        """Return the id of the first available device, or raise if none exist."""
        devices = self.get_devices()
        if not devices:
            raise ThingsBoardAPIError("No devices available for this tenant")
        device_id = devices[0]["id"]["id"]
        logger.info("Using first device id=%s name=%s", device_id, devices[0].get("name"))
        return device_id

    # ------------------------------------------------------------- telemetry
    def get_telemetry(self, device_id: str, keys: list[str] | None = None) -> dict[str, Any]:
        """Return the latest timeseries telemetry for a device.

        GET /api/plugins/telemetry/DEVICE/{deviceId}/values/timeseries
        """
        self._require_token()
        params = {"keys": ",".join(keys)} if keys else None
        response = self._session.get(
            self._config.telemetry_endpoint(device_id),
            params=params,
            timeout=self._config.default_timeout_ms / 1000,
        )
        if response.status_code != 200:
            raise ThingsBoardAPIError(
                f"Get telemetry failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()

    def get_telemetry_with_retry(self, device_id: str) -> dict[str, Any]:
        """Fetch telemetry, retrying while the payload is empty.

        Telemetry can lag behind device provisioning, so we poll rather than
        fail on the first empty read.
        """
        success, data = poll_until(
            action=lambda: self.get_telemetry(device_id),
            predicate=lambda payload: bool(payload),
            retries=self._config.api_retries,
            interval_seconds=self._config.poll_interval_seconds,
            description="telemetry availability",
        )
        if not success:
            logger.warning("Telemetry still empty after %d attempts", self._config.api_retries)
        return data
