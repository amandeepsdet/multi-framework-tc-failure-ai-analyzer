"""DEMO tests for the AI Failure Analysis Engine & QA Assistant.

These two tests FAIL ON PURPOSE so you can watch the AI engine classify a
real UI locator failure and a real API/backend failure end-to-end.

    Run them with the engine ON:
        $env:AI_ENABLED="true"
        pytest tests/test_ai_demo.py -v -o addopts=""

Delete this file when you are done demoing (it is not part of the real suite).
"""

from __future__ import annotations

import allure
import pytest

from pages.login_page import LoginPage
from utils.api_client import ThingsBoardAPIClient
from utils.config import config
from utils.logger import get_logger

logger = get_logger("test_ai_demo")


# --------------------------------------------------------------------------- #
# DEMO 1: UI automation with a WRONG LOCATOR                                   #
# --------------------------------------------------------------------------- #
@allure.feature("DEMO - AI Engine")
@allure.story("UI locator failure")
@allure.title("DEMO-UI: Wrong locator makes the element wait time out")
@pytest.mark.ui
def test_demo_wrong_locator(login_page: LoginPage) -> None:
    """The selector below is intentionally wrong, so Playwright times out.

    Expected AI classification: category=Locator/Element, with a suggested
    correct selector from the LocatorAnalyzer.
    """
    logger.info("START test_demo_wrong_locator")
    # Real selector is  input[formcontrolname='username']  — this one is wrong:
    wrong = login_page.page.locator("input#totally-wrong-username-id")
    wrong.wait_for(state="visible", timeout=3000)  # -> TimeoutError (locator)
    assert wrong.is_visible(), "Username field not found with the given locator"
    logger.info("END test_demo_wrong_locator")


# --------------------------------------------------------------------------- #
# DEMO 2: API automation with a BACKEND / AUTH FAILURE                        #
# --------------------------------------------------------------------------- #
@allure.feature("DEMO - AI Engine")
@allure.story("API backend failure")
@allure.title("DEMO-API: Authentication request is rejected by the backend")
@pytest.mark.api
def test_demo_api_backend_failure(api_client: ThingsBoardAPIClient) -> None:
    """Send a login request with a wrong password.

    The ThingsBoard backend responds with HTTP 401, the client raises
    ThingsBoardAPIError, and the AI engine should classify this as an
    Authentication failure routed to the Identity / Auth team.
    """
    logger.info("START test_demo_api_backend_failure")
    client = ThingsBoardAPIClient()
    token = client.login_with(config.username, "this-password-is-wrong")
    assert token, "Expected a JWT token from the login call"
    logger.info("END test_demo_api_backend_failure")
