"""Reporting tests: all formats render, registry works, bug report builds."""

from __future__ import annotations

import json

import pytest

from aiqa import FailureAnalyzer, FailureContextBuilder, available_formats, get_reporter
from aiqa.reporting import BugReportBuilder, register_reporter
from aiqa.core.interfaces import Reporter

pytestmark = pytest.mark.sdk


def _result_and_ctx():
    ctx = (
        FailureContextBuilder()
        .with_test("suite::test", framework="playwright")
        .with_network([{"status": 500}])
        .with_execution(environment="staging", browser="chromium")
        .build()
    )
    return FailureAnalyzer().analyze(ctx), ctx


def test_all_builtin_formats_available():
    assert set(available_formats()) >= {"markdown", "json", "html", "console"}


@pytest.mark.parametrize("fmt", ["markdown", "json", "html", "console"])
def test_each_reporter_renders_nonempty(fmt):
    result, ctx = _result_and_ctx()
    out = get_reporter(fmt).render(result, ctx)
    assert isinstance(out, str) and out.strip()


def test_json_reporter_is_valid_json():
    result, ctx = _result_and_ctx()
    payload = json.loads(get_reporter("json").render(result, ctx))
    assert payload["analysis"]["root_cause"]["category"] == "Backend"


def test_bug_report_is_generic_and_prioritized():
    result, ctx = _result_and_ctx()
    bug = BugReportBuilder().build(result, ctx)
    assert bug.title.startswith("[Backend]")
    assert bug.priority == "P1"  # Critical -> P1
    assert bug.steps  # has reproduction steps
    md = BugReportBuilder.to_markdown(bug)
    assert "Steps to reproduce" in md


def test_custom_reporter_extension_point():
    @register_reporter
    class CsvReporter(Reporter):
        format = "csv"

        def render(self, result, context=None):
            return f"category,{result.category.value}"

    out = get_reporter("csv").render(_result_and_ctx()[0])
    assert out == "category,Backend"


def test_unknown_format_raises():
    with pytest.raises(KeyError):
        get_reporter("does-not-exist")
