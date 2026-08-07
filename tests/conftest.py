"""Pytest configuration for the AIQA repository.

The test suite here is **framework-agnostic**: it exercises the ``aiqa`` SDK and
the backward-compatible ``qa_ai_engine`` package directly, with no browser or
application under test.

Two optional, opt-in integrations are wired into the pytest lifecycle so a run
can demonstrate the product end to end:

* **AIQA Quality Intelligence portal** — aggregates every run into a historical
  dashboard at ``reports/index.html`` (enable with ``AIQA_PORTAL`` or
  ``AI_ENABLED``). Its history is never wiped, so runs accumulate over time.
* **qa_ai_engine consolidated report** — the packaged pytest plugin's per-run AI
  report (enable with ``AI_ENABLED``).

Both default to OFF, are wrapped in ``try/except``, and can never fail a run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from utils.logger import get_logger

logger = get_logger("conftest")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------- qa_ai_engine (opt-in)
try:  # Import is cheap and guarded so a broken AI install never blocks the suite.
    from qa_ai_engine import ai_config as _ai_config
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


# --------------------------------------- AIQA Quality Intelligence portal (opt-in)
_AIQA_PORTAL = None  # lazily constructed singleton


def _portal_enabled() -> bool:
    flag = os.getenv("AIQA_PORTAL", os.getenv("AI_ENABLED", "false"))
    return flag.strip().lower() in ("1", "true", "yes", "on")


def _get_portal():
    """Return a cached QualityPortal writing into the project reports/ folder."""
    global _AIQA_PORTAL
    if _AIQA_PORTAL is None:
        from aiqa.reporting import QualityPortal

        _AIQA_PORTAL = QualityPortal(_PROJECT_ROOT / "reports")
    return _AIQA_PORTAL


# ----------------------------------------------------- outcome + failure hooks
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record pass/skip totals and, on failure, run framework-agnostic analysis."""
    outcome = yield
    report = outcome.get_result()

    if _ai_enabled():
        try:
            engine = _get_ai_engine()
            if report.when == "setup" and report.skipped:
                engine.append_skipped(item.nodeid)
            elif report.when == "call" and report.passed:
                engine.append_success(item.nodeid)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not record test outcome for AI report: %s", exc)

    if _portal_enabled():
        try:
            portal = _get_portal()
            if report.when == "setup" and report.skipped:
                portal.add_skipped(item.nodeid)
            elif report.when == "call" and report.passed:
                portal.add_success(item.nodeid)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not record test outcome for AIQA portal: %s", exc)

    if report.when != "call" or not report.failed:
        return

    if _portal_enabled() and not getattr(item, "_aiqa_done", False):
        item._aiqa_done = True
        _aiqa_record_failure(item, call, report)


def pytest_sessionstart(session) -> None:
    """Open a fresh consolidated AI report + AIQA portal run (opt-in)."""
    if _ai_enabled():
        try:
            _get_ai_engine().begin_execution()
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not start AI execution report: %s", exc)
    if _portal_enabled():
        try:
            import platform

            from aiqa import __version__ as _aiqa_version

            _get_portal().begin_run(
                framework="pytest",
                environment=os.getenv("AIQA_ENV", ""),
                python_version=platform.python_version(),
                package_version=_aiqa_version,
            )
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not start AIQA portal run: %s", exc)


def pytest_sessionfinish(session, exitstatus) -> None:
    """Render ONE consolidated AI dashboard + refresh the AIQA portal (opt-in)."""
    if _ai_enabled():
        try:
            engine = _get_ai_engine()
            if engine.report_builder.has_data:
                paths = engine.finish_execution()
                html_path = paths.get("html")
                if html_path is not None:
                    logger.info("AI failure-analysis dashboard generated: %s", html_path)
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not finalise AI execution report: %s", exc)

    if _portal_enabled():
        try:
            portal = _get_portal()
            if portal.has_data:
                run = portal.finish_run()
                logger.info(
                    "AIQA Quality Intelligence portal updated: %s (run %s)",
                    _PROJECT_ROOT / "reports" / "index.html",
                    run.run_id if run else "n/a",
                )
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            logger.debug("Could not finalise AIQA portal: %s", exc)


def _aiqa_record_failure(item, call, report) -> None:
    """Build a FailureContext via the generic pytest adapter, analyse it, and add
    the result to the portal run. Reuses AIQA unchanged; never raises into a run.
    """
    try:
        from aiqa import FailureAnalyzer
        from aiqa.adapters.pytest_adapter import PytestAdapter

        exc = call.excinfo.value if call.excinfo else None
        assertion = report.longreprtext[:1000] if hasattr(report, "longreprtext") else ""
        context = PytestAdapter().collect_failure_context(
            exception=exc,
            test_name=item.nodeid,
            item=item,
            call=call,
            report=report,
            assertion_message=assertion,
            environment=os.getenv("AIQA_ENV", ""),
        )
        result = FailureAnalyzer().analyze(context)
        _get_portal().add_failure(result, context)
    except Exception as exc:  # noqa: BLE001 - the portal must never break the run
        logger.warning("AIQA portal failure recording skipped: %s", exc)
