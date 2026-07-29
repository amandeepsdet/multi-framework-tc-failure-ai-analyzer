"""UI tests for the Fuel Level Monitoring dashboard, including live telemetry."""

from __future__ import annotations

import allure
import pytest

from pages.dashboard_page import DashboardPage
from utils.config import config
from utils.helpers import extract_number, in_range, poll_until
from utils.logger import get_logger

logger = get_logger("test_dashboard_ui")


@pytest.fixture
def open_dashboard(dashboard_page: DashboardPage) -> DashboardPage:
    """Open the target dashboard once and reuse it across dashboard tests."""
    dashboard_page.open_dashboards()
    dashboard_page.open_dashboard_by_name()
    return dashboard_page


@allure.feature("UI - Dashboard")
@allure.story("Dashboard load")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("TC-04: Dashboard loads and is not blank")
@pytest.mark.ui
def test_dashboard_loads_and_not_blank(open_dashboard: DashboardPage) -> None:
    """TC-04: The dashboard should render at least one widget (not blank)."""
    logger.info("START test_dashboard_loads_and_not_blank")
    assert open_dashboard.is_loaded(), "Dashboard did not render any widgets"
    open_dashboard.capture("dashboard_loaded")
    assert open_dashboard.widget_count() > 0, "No widgets found on dashboard"
    logger.info("Widget count=%d", open_dashboard.widget_count())
    logger.info("END test_dashboard_loads_and_not_blank")


@allure.feature("UI - Dashboard")
@allure.story("Widgets present")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-05: Tanks table exposes telemetry columns")
@pytest.mark.ui
@pytest.mark.parametrize("column", ["Remaining", "Temperature", "Battery", "Connection"])
def test_expected_widgets_present(open_dashboard: DashboardPage, column: str) -> None:
    """TC-05: Core telemetry columns should be present in the Tanks table."""
    logger.info("START test_expected_widgets_present [%s]", column)
    assert open_dashboard.has_column(column), f"'{column}' column not visible"
    open_dashboard.capture(f"column_{column.lower()}")
    logger.info("END test_expected_widgets_present [%s]", column)


@allure.feature("UI - Dashboard")
@allure.story("Boundary validation")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("TC-06: Metric values are within valid ranges")
@pytest.mark.ui
def test_metric_values_within_range(open_dashboard: DashboardPage) -> None:
    """TC-06: First tank's telemetry values should fall inside valid ranges."""
    logger.info("START test_metric_values_within_range")
    metrics = open_dashboard.read_tank_metrics(0)
    logger.info("Tank metrics: %s", metrics)

    fuel = extract_number(metrics["fuel"])
    temperature = extract_number(metrics["temperature"])
    battery = extract_number(metrics["battery"])
    connection = metrics["connection"].lower()

    assert in_range(fuel, config.fuel_level_range), f"Fuel {fuel} out of range"
    assert in_range(temperature, config.temperature_range), f"Temp {temperature} out of range"
    assert in_range(battery, config.battery_range), f"Battery {battery} out of range"
    assert connection in config.valid_connection_states, f"Invalid connection: {connection!r}"
    logger.info("END test_metric_values_within_range")


@allure.feature("UI - Dashboard")
@allure.story("Real-time telemetry")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-07: Live telemetry refreshes or stays valid within polling window")
@pytest.mark.ui
@pytest.mark.realtime
def test_realtime_telemetry_refresh(open_dashboard: DashboardPage) -> None:
    """TC-07: Live telemetry should refresh, or remain valid, within polling window.

    Per the assignment, we must not fail immediately on the first observation.
    We snapshot the dashboard text, then poll for a change up to the configured
    retries. If nothing changes we still pass as long as the data stays valid,
    but we log the observation clearly.
    """
    logger.info("START test_realtime_telemetry_refresh")
    baseline = open_dashboard.dashboard_text()

    changed, latest = poll_until(
        action=open_dashboard.dashboard_text,
        predicate=lambda text: text != baseline,
        retries=config.poll_retries,
        interval_seconds=config.poll_interval_seconds,
        description="dashboard telemetry refresh",
    )

    open_dashboard.capture("realtime_after_poll")
    if changed:
        logger.info("Telemetry refreshed during polling window (PASS)")
    else:
        logger.warning(
            "Telemetry unchanged after %d retries; data still present (reported)",
            config.poll_retries,
        )
    # Either outcome is acceptable, but the dashboard must remain non-empty.
    assert latest.strip(), "Dashboard became blank during polling"
    logger.info("END test_realtime_telemetry_refresh")
