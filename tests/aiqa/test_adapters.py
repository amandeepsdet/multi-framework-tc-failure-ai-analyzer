"""Adapter tests: each adapter yields a valid, generic FailureContext."""

from __future__ import annotations

import json

import pytest

from aiqa import FailureContext
from aiqa.adapters import (
    GenericAdapter,
    PlaywrightAdapter,
    PytestAdapter,
    RobotFrameworkAdapter,
    SeleniumAdapter,
)

pytestmark = pytest.mark.sdk


def test_generic_adapter_from_dict_and_json_string():
    payload = {"metadata": {"test_name": "t"}, "exception": {"message": "http 500"}}
    ctx = GenericAdapter().collect_failure_context(payload)
    assert isinstance(ctx, FailureContext)
    assert ctx.test_name == "t"

    ctx2 = GenericAdapter().collect_failure_context(json.dumps(payload))
    assert ctx2.test_name == "t"


def test_playwright_adapter_with_duck_typed_page():
    class FakePage:
        url = "http://app/login"

        def title(self):
            return "Login"

        def content(self):
            return "<html>login</html>"

    ctx = PlaywrightAdapter(page=FakePage()).collect_failure_context(
        TimeoutError("locator #x not found"), test_name="ui::test", browser="chromium"
    )
    assert ctx.metadata.framework == "playwright"
    assert ctx.execution.url == "http://app/login"
    assert ctx.evidence.dom_snapshot


def test_selenium_adapter_with_duck_typed_driver():
    class FakeDriver:
        current_url = "http://app/orders"
        title = "Orders"
        page_source = "<html>orders</html>"

        def get_log(self, _):
            return [{"level": "SEVERE", "message": "TypeError"}]

    ctx = SeleniumAdapter(driver=FakeDriver()).collect_failure_context(
        Exception("no such element"), test_name="orders::test"
    )
    assert ctx.metadata.framework == "selenium"
    assert ctx.evidence.console and ctx.evidence.console[0].level == "severe"


def test_pytest_adapter_from_plain_exception():
    ctx = PytestAdapter().collect_failure_context(
        AssertionError("expected 200 got 503"), test_name="api::test"
    )
    assert ctx.metadata.framework == "pytest"
    assert "503" in ctx.assertion_message or "503" in ctx.exception.message


def test_robotframework_adapter():
    ctx = RobotFrameworkAdapter().collect_failure_context(
        test_name="Login Works", message="Element not visible", suite="Login"
    )
    assert ctx.metadata.framework == "robotframework"
    assert ctx.metadata.suite == "Login"
    assert ctx.evidence.custom["robot_status"] == "FAIL"


def test_adapters_never_import_frameworks_at_module_load():
    # Importing the adapters package must not require playwright/selenium/pytest
    # to be installed. This simply asserts the classes are importable.
    assert PlaywrightAdapter.name == "playwright"
    assert SeleniumAdapter.name == "selenium"
