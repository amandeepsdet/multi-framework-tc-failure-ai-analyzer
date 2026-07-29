"""Shared pytest fixtures for UI and API test suites.

Fixtures centralise setup/teardown (browser context, authenticated pages, API
client) so individual tests remain short and declarative. A failure hook also
captures a screenshot for any failing UI test, and a session hook wipes stale
reports/screenshots so every run starts clean.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Page

from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from utils.api_client import ThingsBoardAPIClient
from utils.helpers import screenshot_path
from utils.logger import get_logger

logger = get_logger("conftest")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------- AI engine (opt-in)
# The AI Failure Analysis Engine is entirely optional and defaults to OFF, so
# existing runs are unaffected. When AI_ENABLED=true it collects evidence on a
# failing test and produces a root-cause analysis + bug report.
try:  # Import is cheap and side-effect free; guard so a broken AI install never
    from qa_ai_engine import ai_config as _ai_config  # blocks the core test suite.
except Exception as _ai_import_exc:  # noqa: BLE001  # pragma: no cover
    _ai_config = None
    logger.warning("AI engine unavailable (%s); continuing without it", _ai_import_exc)

_AI_ENGINE = None  # lazily constructed singleton


def _ai_enabled() -> bool:
    return bool(_ai_config is not None and _ai_config.enabled)


def _get_ai_engine():
    """Return a cached AIEngine instance, building it on first use."""
    global _AI_ENGINE
    if _AI_ENGINE is None:
        from qa_ai_engine import AIEngine

        _AI_ENGINE = AIEngine()
    return _AI_ENGINE


def pytest_configure(config: pytest.Config) -> None:
    """Delete previous screenshots and HTML report so each run is fresh.

    Allure results are cleaned separately via ``--clean-alluredir`` in pytest.ini.
    Locked files (e.g. still syncing via OneDrive) are skipped rather than failing.
    """
    screenshots = _PROJECT_ROOT / "screenshots"
    if screenshots.exists():
        for item in screenshots.iterdir():
            if item.name == ".gitkeep":
                continue
            try:
                shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink()
            except OSError:
                pass

    html_report = _PROJECT_ROOT / "reports" / "report.html"
    if html_report.exists():
        try:
            html_report.unlink()
        except OSError:
            pass


# ------------------------------------------------------------- API automation
@pytest.fixture(scope="session")
def api_client() -> ThingsBoardAPIClient:
    """Return an authenticated ThingsBoard API client for the session."""
    client = ThingsBoardAPIClient()
    client.login()
    return client


# -------------------------------------------------------------- UI automation
@pytest.fixture
def login_page(page: Page) -> LoginPage:
    """Return a LoginPage opened at the login screen."""
    return LoginPage(page).open()


@pytest.fixture
def authenticated_page(page: Page) -> Iterator[Page]:
    """Log in via the UI and yield an authenticated page.

    Centralising login here means dashboard tests never repeat the login flow.
    """
    logger.info("Fixture: authenticating UI session")
    login = LoginPage(page).open()
    login.login()
    login.wait_for_login_success()
    login.capture("login_success")
    yield page


@pytest.fixture
def dashboard_page(authenticated_page: Page) -> DashboardPage:
    """Return a DashboardPage on an already-authenticated session."""
    return DashboardPage(authenticated_page)


# --------------------------------------------- AI evidence recorder (autouse, opt-in)
@pytest.fixture(autouse=True)
def _ai_event_recorder(request: pytest.FixtureRequest):
    """Attach a console/network recorder to the page for AI evidence collection.

    Only activates for UI tests (those requesting the ``page`` fixture) and only
    when AI is enabled, so API tests and default runs incur zero overhead.
    """
    if _ai_enabled() and "page" in request.fixturenames:
        try:
            from qa_ai_engine import PageEventRecorder

            page = request.getfixturevalue("page")
            request.node._ai_recorder = PageEventRecorder(page)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not attach AI recorder: %s", exc)
    yield


# ---------------------------------------------------- screenshot-on-failure hook
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when a UI test fails, then run AI analysis (opt-in)."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    page = item.funcargs.get("page") or item.funcargs.get("authenticated_page")
    screenshot_file: str | None = None
    if page is not None:
        screenshot_file = screenshot_path(f"FAILURE_{item.name}")
        try:
            page.screenshot(path=screenshot_file, full_page=True)
            logger.error("Failure screenshot saved: %s", screenshot_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not capture failure screenshot: %s", exc)
            screenshot_file = None

    if _ai_enabled():
        _run_ai_analysis(item, call, report, page, screenshot_file)


def _run_ai_analysis(item, call, report, page, screenshot_file) -> None:
    """Collect evidence, run root-cause analysis, and attach outputs."""
    try:
        engine = _get_ai_engine()
        exception = call.excinfo.value if call.excinfo else None
        recorder = getattr(item, "_ai_recorder", None)
        exec_time = getattr(call, "stop", 0) - getattr(call, "start", 0)
        browser = item.funcargs.get("browser_name", "") if hasattr(item, "funcargs") else ""

        outcome = engine.analyze_failure(
            test_name=item.nodeid,
            exception=exception,
            page=page,
            recorder=recorder,
            screenshot=screenshot_file,
            assertion_message=report.longreprtext[:1000] if hasattr(report, "longreprtext") else "",
            browser=browser,
            execution_time_s=round(exec_time, 3) if exec_time else None,
        )
        analysis = outcome.analysis
        logger.error(
            "AI analysis: %s (%s, confidence=%d%%) — owner=%s",
            analysis.root_cause,
            analysis.category.value,
            analysis.confidence,
            analysis.owner,
        )
        _attach_ai_to_allure(engine, outcome)
        _attach_ai_to_html(item, report, engine, outcome)
    except Exception as exc:  # noqa: BLE001 - AI must never break the run
        logger.warning("AI failure analysis skipped due to error: %s", exc)


def _attach_ai_to_allure(engine, outcome) -> None:
    try:
        import allure

        analysis = outcome.analysis
        summary = (
            f"Root Cause: {analysis.root_cause}\n"
            f"Category: {analysis.category.value}\n"
            f"Confidence: {analysis.confidence}%\n"
            f"Severity: {analysis.severity.value}\n"
            f"Likely Owner: {analysis.owner}\n"
            f"Recommended Fix: {analysis.recommended_fix}\n"
            f"Evidence:\n- " + "\n- ".join(analysis.evidence)
        )
        allure.attach(summary, name="AI Root Cause Analysis", attachment_type=allure.attachment_type.TEXT)
        allure.attach(
            engine.bug_gen.to_markdown(outcome.bug_report),
            name="AI Bug Report",
            attachment_type=allure.attachment_type.TEXT,
        )
        allure.attach(
            outcome.analysis.to_json(),
            name="AI Analysis JSON",
            attachment_type=allure.attachment_type.JSON,
        )
        allure.attach(
            outcome.record.to_json(),
            name="Failure Evidence JSON",
            attachment_type=allure.attachment_type.JSON,
        )
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        logger.debug("Could not attach AI results to Allure: %s", exc)


def _attach_ai_to_html(item, report, engine, outcome) -> None:
    try:
        from pytest_html import extras  # type: ignore

        html_fragment = engine.report_gen.to_html(outcome.record, outcome.analysis)
        current = list(getattr(report, "extras", []))
        current.append(extras.html(html_fragment))
        report.extras = current
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        logger.debug("Could not attach AI results to pytest-html: %s", exc)
