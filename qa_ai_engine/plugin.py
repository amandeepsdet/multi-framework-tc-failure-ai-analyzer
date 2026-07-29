"""Pytest plugin: automatic AI failure analysis for any Playwright project.

Install the ``qa-ai-engine`` package and this plugin is auto-discovered by
pytest (via the ``pytest11`` entry point). With ``AI_ENABLED=true`` set, every
failing test that uses the pytest-playwright ``page`` fixture is analysed:
root cause, category, confidence, likely owner, and a tracker-ready bug report
are produced, persisted to the history/vector store, and attached to Allure and
pytest-html reports.

The plugin is a **no-op** unless ``AI_ENABLED`` is true, so it never affects
normal runs. Set ``QA_AI_DISABLE_PLUGIN=true`` to force it off even when enabled
(useful when a project wires the engine manually in its own ``conftest.py``).

Zero required configuration; works fully offline with the built-in heuristic
provider. Point ``AI_PROVIDER`` at an LLM to upgrade the analysis.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pytest

try:  # The engine is optional; never let its absence break test collection.
    from qa_ai_engine import AIEngine, PageEventRecorder, ai_config
    from qa_ai_engine._logging import get_logger

    _IMPORT_OK = True
except Exception as _exc:  # noqa: BLE001  # pragma: no cover
    _IMPORT_OK = False

    import logging

    def get_logger(name: str = "qa_ai") -> logging.Logger:  # type: ignore[misc]
        return logging.getLogger(name)


logger = get_logger("qa_ai.pytest")

_ENGINE: "AIEngine | None" = None


def _plugin_active() -> bool:
    """True only when the engine imported, AI is enabled, and not force-disabled."""
    if not _IMPORT_OK:
        return False
    if os.getenv("QA_AI_DISABLE_PLUGIN", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return bool(ai_config.enabled)


def _get_engine() -> "AIEngine":
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AIEngine()
    return _ENGINE


# --------------------------------------------------------------- evidence capture
@pytest.fixture(autouse=True)
def _qa_ai_recorder(request: pytest.FixtureRequest):
    """Attach a console/network recorder to the Playwright ``page`` (opt-in).

    Only activates for tests that request the ``page`` fixture and only when the
    engine is active, so API-only tests and default runs incur zero overhead.
    """
    if _plugin_active() and "page" in request.fixturenames:
        try:
            page = request.getfixturevalue("page")
            request.node._qa_ai_recorder = PageEventRecorder(page)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not attach AI recorder: %s", exc)
    yield


# ------------------------------------------------------------- analysis on failure
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    """Run AI failure analysis when a test fails during its ``call`` phase."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    if getattr(item, "_qa_ai_done", False) or not _plugin_active():
        return
    item._qa_ai_done = True  # type: ignore[attr-defined]
    try:
        _analyze(item, call, report)
    except Exception as exc:  # noqa: BLE001 - AI must never break the run
        logger.warning("AI failure analysis skipped due to error: %s", exc)


def _find_page(item: pytest.Item):
    funcargs = getattr(item, "funcargs", {})
    for name in ("page", "authenticated_page"):
        page = funcargs.get(name)
        if page is not None:
            return page
    return None


def _capture_screenshot(page, item: pytest.Item) -> "str | None":
    if page is None:
        return None
    try:
        ai_config.ensure_dirs()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() else "_" for c in item.name)[:60]
        path = ai_config.reports_dir / f"FAILURE_{stamp}_{safe}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not capture failure screenshot: %s", exc)
        return None


def _analyze(item: pytest.Item, call: pytest.CallInfo[Any], report: Any) -> None:
    engine = _get_engine()
    page = _find_page(item)
    screenshot = _capture_screenshot(page, item)
    exception = call.excinfo.value if call.excinfo else None
    recorder = getattr(item, "_qa_ai_recorder", None)
    exec_time = getattr(call, "stop", 0) - getattr(call, "start", 0)
    funcargs = getattr(item, "funcargs", {})
    browser = funcargs.get("browser_name", "") if isinstance(funcargs, dict) else ""

    result = engine.analyze_failure(
        test_name=item.nodeid,
        exception=exception,
        page=page,
        recorder=recorder,
        screenshot=screenshot,
        assertion_message=report.longreprtext[:1000] if hasattr(report, "longreprtext") else "",
        browser=browser,
        execution_time_s=round(exec_time, 3) if exec_time else None,
    )
    analysis = result.analysis
    logger.error(
        "AI analysis: %s (%s, confidence=%d%%) — owner=%s",
        analysis.root_cause,
        analysis.category.value,
        analysis.confidence,
        analysis.owner,
    )
    _attach_allure(engine, result)
    _attach_html(report, engine, result)


def _attach_allure(engine: "AIEngine", result: Any) -> None:
    try:
        import allure  # type: ignore

        analysis = result.analysis
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
            engine.bug_gen.to_markdown(result.bug_report),
            name="AI Bug Report",
            attachment_type=allure.attachment_type.TEXT,
        )
        allure.attach(analysis.to_json(), name="AI Analysis JSON", attachment_type=allure.attachment_type.JSON)
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        logger.debug("Could not attach AI results to Allure: %s", exc)


def _attach_html(report: Any, engine: "AIEngine", result: Any) -> None:
    try:
        from pytest_html import extras  # type: ignore

        fragment = engine.report_gen.to_html(result.record, result.analysis)
        current = list(getattr(report, "extras", []))
        current.append(extras.html(fragment))
        report.extras = current
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        logger.debug("Could not attach AI results to pytest-html: %s", exc)
