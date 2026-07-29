"""API tests: authentication, device discovery, telemetry, and negative paths.

Annotated with Allure metadata (feature/story/severity) so the generated report
groups scenarios and highlights negative / security cases.
"""

from __future__ import annotations

import numbers

import allure
import pytest

from utils.api_client import ThingsBoardAPIClient, ThingsBoardAPIError
from utils.config import config
from utils.logger import get_logger

logger = get_logger("test_api_telemetry")


@allure.feature("API - Authentication")
@allure.story("Valid login")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("TC-08: API authentication returns a JWT token")
@pytest.mark.api
def test_api_authentication_returns_token(api_client: ThingsBoardAPIClient) -> None:
    """Login should return a non-empty JWT token."""
    logger.info("START test_api_authentication_returns_token")
    assert api_client.token, "No JWT token returned from login"
    logger.info("END test_api_authentication_returns_token")


@allure.feature("API - Authentication")
@allure.story("Unauthorized access")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-09: Protected endpoint rejects requests without a token")
@pytest.mark.api
@pytest.mark.negative
def test_unauthorized_request_is_rejected() -> None:
    """Calling a protected endpoint without a token should fail."""
    logger.info("START test_unauthorized_request_is_rejected")
    client = ThingsBoardAPIClient()  # deliberately not logged in
    with pytest.raises(ThingsBoardAPIError):
        client.get_devices()
    logger.info("END test_unauthorized_request_is_rejected")


@allure.feature("API - Authentication")
@allure.story("Invalid credentials")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-13: Login with wrong password is rejected")
@pytest.mark.api
@pytest.mark.negative
def test_login_with_wrong_password_rejected() -> None:
    """A valid username with an incorrect password must not authenticate."""
    logger.info("START test_login_with_wrong_password_rejected")
    client = ThingsBoardAPIClient()
    with pytest.raises(ThingsBoardAPIError) as exc:
        client.login_with(config.username, "definitely-wrong-password")
    assert "401" in str(exc.value), f"Expected 401, got: {exc.value}"
    logger.info("END test_login_with_wrong_password_rejected")


@allure.feature("API - Authentication")
@allure.story("Expired / invalid token")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-14: Expired or tampered JWT token is rejected")
@pytest.mark.api
@pytest.mark.negative
def test_expired_or_invalid_token_rejected() -> None:
    """A tampered/expired JWT must be rejected by protected endpoints.

    We take the configured token (or a placeholder) and corrupt its signature,
    which the server treats the same way as an expired token: 401 Unauthorized.
    """
    logger.info("START test_expired_or_invalid_token_rejected")
    base_token = config.jwt_token or "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ4In0"
    tampered_token = base_token[:-4] + "AAAA"  # break the signature

    client = ThingsBoardAPIClient()
    client.use_token(tampered_token)
    with pytest.raises(ThingsBoardAPIError) as exc:
        client.get_devices()
    assert any(code in str(exc.value) for code in ("401", "403")), (
        f"Expected 401/403 for invalid token, got: {exc.value}"
    )
    logger.info("END test_expired_or_invalid_token_rejected")


@allure.feature("API - Devices")
@allure.story("Device discovery")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-10: Device list endpoint returns tenant devices")
@pytest.mark.api
def test_get_devices_returns_data(api_client: ThingsBoardAPIClient) -> None:
    """Device list endpoint should return at least one device."""
    logger.info("START test_get_devices_returns_data")
    devices = api_client.get_devices()
    assert isinstance(devices, list), "Device response is not a list"
    assert devices, "No devices returned for tenant"
    assert "id" in devices[0] and "id" in devices[0]["id"], "Device id missing"
    logger.info("END test_get_devices_returns_data")


@allure.feature("API - Telemetry")
@allure.story("Missing device")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("TC-15: Telemetry for a non-existent device is handled")
@pytest.mark.api
@pytest.mark.negative
def test_missing_device_telemetry_is_handled(api_client: ThingsBoardAPIClient) -> None:
    """Requesting telemetry for a bogus device id should error.

    ThingsBoard returns 4xx for a malformed/unknown device id; the client
    surfaces that as ThingsBoardAPIError.
    """
    logger.info("START test_missing_device_telemetry_is_handled")
    bogus_device_id = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ThingsBoardAPIError):
        api_client.get_telemetry(bogus_device_id)
    logger.info("END test_missing_device_telemetry_is_handled")


@allure.feature("API - Telemetry")
@allure.story("Telemetry retrieval")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-11: Telemetry returns valid JSON structure and types")
@pytest.mark.api
def test_get_telemetry_structure_and_types(api_client: ThingsBoardAPIClient) -> None:
    """Telemetry should return a JSON object with valid value types."""
    logger.info("START test_get_telemetry_structure_and_types")
    device_id = api_client.get_first_device_id()
    telemetry = api_client.get_telemetry_with_retry(device_id)

    assert isinstance(telemetry, dict), "Telemetry payload is not a JSON object"

    # Each key maps to a list of {ts, value} records; validate shape when present.
    for key, samples in telemetry.items():
        assert isinstance(samples, list) and samples, f"No samples for key '{key}'"
        record = samples[0]
        assert "ts" in record and "value" in record, f"Malformed record for '{key}'"
        assert isinstance(record["ts"], numbers.Number), "Timestamp is not numeric"
        logger.info("Telemetry key=%s sample=%s", key, record)

    if not telemetry:
        logger.warning("Telemetry empty after retries; device may be idle (reported)")
    logger.info("END test_get_telemetry_structure_and_types")


@allure.feature("API - Telemetry")
@allure.story("Boundary validation")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("TC-12: Telemetry values fall within valid ranges")
@pytest.mark.api
def test_telemetry_values_within_ranges(api_client: ThingsBoardAPIClient) -> None:
    """Known numeric telemetry keys should fall within valid ranges."""
    logger.info("START test_telemetry_values_within_ranges")
    device_id = api_client.get_first_device_id()
    telemetry = api_client.get_telemetry_with_retry(device_id)

    range_map = {
        "fuelLevel": config.fuel_level_range,
        "temperature": config.temperature_range,
        "battery": config.battery_range,
    }
    for key, bounds in range_map.items():
        if key not in telemetry:
            logger.info("Key '%s' not exposed by device; skipping", key)
            continue
        raw = telemetry[key][0]["value"]
        try:
            value = float(raw)
        except (TypeError, ValueError):
            pytest.fail(f"Telemetry '{key}' value not numeric: {raw!r}")
        low, high = bounds
        assert low <= value <= high, f"{key}={value} outside {bounds}"
        logger.info("Validated %s=%s within %s", key, value, bounds)
    logger.info("END test_telemetry_values_within_ranges")
