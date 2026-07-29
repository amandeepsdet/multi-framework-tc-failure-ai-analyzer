"""Page object for the ThingsBoard login screen."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from utils.config import Config, config

from .base_page import BasePage


class LoginPage(BasePage):
    """Encapsulates the ThingsBoard login form and its interactions."""

    def __init__(self, page: Page, cfg: Config = config) -> None:
        super().__init__(page, cfg)
        self.username_input = page.locator("input[formcontrolname='username']")
        self.password_input = page.locator("input[formcontrolname='password']")
        self.login_button = page.locator("span.mdc-button__label", has_text="Sign in")
        self.error_toast = page.locator(".tb-toast.error-toast")

    def open(self) -> "LoginPage":
        """Open the login page."""
        self.goto("/login")
        self.username_input.wait_for(state="visible", timeout=self.config.default_timeout_ms)
        return self

    def login(self, username: str | None = None, password: str | None = None) -> None:
        """Fill credentials and submit the form."""
        user = username if username is not None else self.config.username
        pwd = password if password is not None else self.config.password
        self.log.info("Logging in as %s", user)

        self.username_input.fill(user)
        self.password_input.fill(pwd)
        self.login_button.click()

    def get_error_toast(self) -> str | None:
        """Return the error toast text if it appears, else None.

        Shown for invalid credentials, e.g. "Invalid username or password".
        """
        try:
            self.error_toast.wait_for(state="visible", timeout=10000)
        except Exception:  # noqa: BLE001 - no toast means no error surfaced
            return None
        text = self.error_toast.inner_text().strip()
        self.log.info("Login error toast: %s", text)
        return text

    def wait_for_login_success(self) -> None:
        """Wait until the app navigates away from the login page (home loaded)."""
        expect(self.page).not_to_have_url(
            f"{self.config.base_url}/login",
            timeout=self.config.default_timeout_ms,
        )
        self.log.info("Login succeeded; current url=%s", self.page.url)
        self.dismiss_welcome_banner()
