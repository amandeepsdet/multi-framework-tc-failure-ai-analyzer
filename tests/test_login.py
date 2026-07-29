"""UI tests for the ThingsBoard login flow."""

from __future__ import annotations

import allure
import pytest

from pages.login_page import LoginPage
from utils.logger import get_logger

logger = get_logger("test_login")


@allure.feature("UI - Login")
@allure.story("Login form")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("TC-01: Login form elements are present")
@pytest.mark.ui
def test_login_form_elements_present(login_page: LoginPage) -> None:
    """TC-01: The username, password, and login controls should be visible."""
    logger.info("START test_login_form_elements_present")
    assert login_page.username_input.is_visible(), "Username field missing"
    assert login_page.password_input.is_visible(), "Password field missing"
    assert login_page.login_button.is_visible(), "Login button missing"
    logger.info("END test_login_form_elements_present")


@allure.feature("UI - Login")
@allure.story("Valid login")
@allure.severity(allure.severity_level.BLOCKER)
@allure.title("TC-02: Valid credentials log the user in")
@pytest.mark.ui
def test_valid_login_succeeds(login_page: LoginPage) -> None:
    """TC-02: Valid credentials should log in and leave the login page."""
    logger.info("START test_valid_login_succeeds")
    login_page.login()
    login_page.wait_for_login_success()
    login_page.capture("login_success_test")
    assert "/login" not in login_page.page.url, "Still on login page after login"
    logger.info("END test_valid_login_succeeds")


@allure.feature("UI - Login")
@allure.story("Invalid credentials")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("TC-03: Invalid credentials do not authenticate")
@pytest.mark.ui
@pytest.mark.negative
def test_invalid_login_shows_error(login_page: LoginPage) -> None:
    """TC-03: Invalid credentials should show an error and not authenticate."""
    logger.info("START test_invalid_login_shows_error")
    login_page.login(username="invalid@example.com", password="WrongPassword123")
    error = login_page.get_error_toast()
    assert error is not None, "No error toast shown for invalid credentials"
    assert "Invalid username or password" in error, f"Unexpected error text: {error!r}"
    assert "/login" in login_page.page.url, "Invalid login unexpectedly succeeded"
    logger.info("END test_invalid_login_shows_error")


@allure.feature("UI - Login")
@allure.story("Empty credentials")
@allure.severity(allure.severity_level.NORMAL)
@allure.title("TC-16: Empty credentials keep the user on the login page")
@pytest.mark.ui
@pytest.mark.negative
def test_empty_credentials_blocks_login(login_page: LoginPage) -> None:
    """TC-16: Submitting empty credentials must not authenticate the user."""
    logger.info("START test_empty_credentials_blocks_login")
    login_page.login(username="", password="")
    login_page.page.wait_for_timeout(2000)
    assert "/login" in login_page.page.url, "Empty login unexpectedly succeeded"
    logger.info("END test_empty_credentials_blocks_login")

