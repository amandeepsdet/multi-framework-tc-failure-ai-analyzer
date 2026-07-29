"""Page object for the ThingsBoard dashboards and the Fuel Level dashboard.

The Fuel Level Monitoring dashboard's key widget is a "Tanks" table where each
row exposes a tank's fuel level, temperature, battery, and connection status as
columns. Telemetry is therefore validated by reading the table cells.
"""

from __future__ import annotations

from playwright.sync_api import Page

from utils.config import Config, config

from .base_page import BasePage


class DashboardPage(BasePage):
    """Encapsulates navigation to and validation of the target dashboard."""

    # Tanks table column CSS classes as rendered by ThingsBoard.
    _COLUMNS = {
        "fuel": "mat-column-def1",
        "temperature": "mat-column-def3",
        "battery": "mat-column-def4",
        "connection": "mat-column-def5",
    }

    def __init__(self, page: Page, cfg: Config = config) -> None:
        super().__init__(page, cfg)
        self.widgets = page.locator("tb-widget, .tb-widget")
        self.tank_rows = page.locator("tb-entities-table-widget tbody mat-row")

    def open_dashboards(self) -> "DashboardPage":
        """Navigate to the Dashboards section of the tenant workspace."""
        self.goto("/dashboards")
        self.page.wait_for_load_state("networkidle")
        self.dismiss_welcome_banner()
        return self

    def open_dashboard_by_name(self, name: str | None = None) -> None:
        """Open a dashboard from the list by name and wait for the Tanks table."""
        target = name or self.config.dashboard_name
        self.log.info("Opening dashboard '%s'", target)
        self.dismiss_welcome_banner()
        row = self.page.get_by_text(target, exact=False).first
        row.wait_for(state="visible", timeout=self.config.default_timeout_ms)
        row.click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_tanks_table()

    def wait_for_tanks_table(self) -> None:
        """Wait until the Tanks table has rendered at least one row."""
        self.tank_rows.first.wait_for(
            state="visible", timeout=self.config.default_timeout_ms
        )

    def is_loaded(self) -> bool:
        """Return True when at least one widget has rendered (not blank)."""
        try:
            self.widgets.first.wait_for(
                state="visible", timeout=self.config.default_timeout_ms
            )
        except Exception:  # noqa: BLE001 - treat any wait failure as "not loaded"
            return False
        return self.widgets.count() > 0

    def widget_count(self) -> int:
        """Return the number of rendered widgets on the dashboard."""
        return self.widgets.count()

    def has_column(self, name: str) -> bool:
        """Return True when a Tanks table column header contains ``name``."""
        header = self.page.locator(".mat-sort-header-content", has_text=name)
        return header.count() > 0 and header.first.is_visible()

    def read_tank_metrics(self, row_index: int = 0) -> dict[str, str]:
        """Return raw cell texts for a tank row (fuel/temperature/battery/connection)."""
        row = self.tank_rows.nth(row_index)
        return {
            key: row.locator(f"mat-cell.{col}").inner_text().strip()
            for key, col in self._COLUMNS.items()
        }

    def dashboard_text(self) -> str:
        """Return the full visible text of the dashboard (used to poll refresh)."""
        return self.page.locator("body").inner_text()
