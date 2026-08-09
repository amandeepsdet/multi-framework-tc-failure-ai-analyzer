"""Tests for the intelligent bug generator and multi-tracker exporters."""

from __future__ import annotations

import json

import pytest

from aiqa import BugExporter, BugGenerationEngine, FailureAnalyzer, FailureContextBuilder

pytestmark = pytest.mark.sdk


def _analyzed(**kw):
    b = FailureContextBuilder().with_test(kw.get("name", "checkout_flow"))
    b.with_exception_text(type=kw.get("exc_type", "Error"), message=kw.get("message", ""))
    if kw.get("network"):
        b.with_network(kw["network"])
    if kw.get("assertion"):
        b.with_assertion(kw["assertion"])
    b.with_execution(environment="staging", browser="chromium")
    b.with_screenshot(kw.get("screenshot"))
    context = b.build()
    return FailureAnalyzer().analyze(context), context


def test_builds_enriched_bug_with_natural_title():
    result, context = _analyzed(network=[{"status": 500, "url": "/api/checkout"}])
    bug = BugGenerationEngine().build(result, context)
    assert "HTTP 500" in bug.title
    assert bug.category == "Backend"
    assert bug.confidence > 0
    assert bug.risk
    assert bug.preventive_action
    assert bug.ai_explanation
    assert bug.environment  # env populated from context
    assert bug.python_version


def test_authentication_title_reads_naturally():
    result, context = _analyzed(network=[{"status": 401, "url": "/login"}])
    bug = BugGenerationEngine().build(result, context)
    assert bug.title.lower().startswith("authentication failed")


def test_exporter_all_formats():
    result, context = _analyzed(network=[{"status": 500, "url": "/api/checkout"}])
    bug = BugGenerationEngine().build(result, context)
    ex = BugExporter()

    assert ex.to_markdown(bug).startswith("# ")
    assert "<html" in ex.to_html(bug).lower()
    assert json.loads(ex.to_json(bug))["title"] == bug.title
    assert bug.title in ex.to_plaintext(bug)

    jira = json.loads(ex.to_jira_json(bug))
    assert jira["fields"]["summary"] == bug.title
    assert jira["fields"]["issuetype"]["name"] == "Bug"

    azure = json.loads(ex.to_azure_json(bug))
    assert any(op["path"] == "/fields/System.Title" for op in azure)

    gh = ex.to_github(bug)
    assert gh["title"] == bug.title and "bug" in gh["labels"]

    linear = json.loads(ex.to_linear_json(bug))
    assert linear["title"] == bug.title


def test_export_all_writes_expected_files(tmp_path):
    result, context = _analyzed(network=[{"status": 500, "url": "/api/checkout"}])
    bug = BugGenerationEngine().build(result, context)
    written = BugExporter().export_all(bug, tmp_path)
    for name in ("bug.md", "bug.html", "bug.json", "jira.json",
                 "azure_work_item.json", "github_issue.md"):
        assert name in written
        assert written[name].exists()
        assert written[name].read_text(encoding="utf-8").strip()


def test_bug_generation_without_context():
    result, _ = _analyzed(message="something odd")
    bug = BugGenerationEngine().build(result, None)
    # No context: still produces a valid, exportable bug.
    assert bug.title
    assert BugExporter().to_markdown(bug)


def test_missing_screenshot_and_logs_are_tolerated():
    result, context = _analyzed(message="locator #foo not found")
    bug = BugGenerationEngine().build(result, context)
    assert isinstance(bug.screenshots, list)
    assert isinstance(bug.logs, list)
