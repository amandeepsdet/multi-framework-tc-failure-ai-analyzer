"""Tests for the ``aiqa`` command-line interface."""

from __future__ import annotations

import json

from aiqa import FailureContextBuilder
from aiqa.cli import main


def _ctx_file(tmp_path):
    context = (
        FailureContextBuilder()
        .with_test("tests/checkout/test_place_order.py::test_place_order")
        .with_exception_text(type="AssertionError", message="expected 200 but got 500")
        .with_network([{"method": "POST", "url": "/api/checkout", "status": 500}])
        .with_execution(environment="staging", browser="chromium")
        .build()
    )
    path = tmp_path / "ctx.json"
    path.write_text(context.to_json(), encoding="utf-8")
    return path


def test_classify_json(tmp_path, capsys):
    rc = main(["classify", str(_ctx_file(tmp_path)), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["category"] == "Backend"
    assert data["risk_level"] == "Critical"
    assert data["owner"]


def test_explain_failure_console(tmp_path, capsys):
    rc = main(["explain-failure", str(_ctx_file(tmp_path))])
    assert rc == 0
    out = capsys.readouterr().out
    assert "AIQA" in out
    assert "confidence" in out.lower()


def test_explain_failure_json(tmp_path, capsys):
    rc = main(["explain-failure", str(_ctx_file(tmp_path)), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["reasoning_detail"]["reasoning_points"]


def test_heal_locator(tmp_path, capsys):
    dom = tmp_path / "dom.html"
    dom.write_text("<button data-testid='order' class='b'>Place order</button>", encoding="utf-8")
    rc = main(
        ["heal-locator", "--old", "button.place-order", "--dom", str(dom), "--text", "Place order"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "get_by_test_id('order')" in out


def test_heal_locator_json(tmp_path, capsys):
    dom = tmp_path / "dom.html"
    dom.write_text("<button id='save'>Save</button>", encoding="utf-8")
    rc = main(["heal-locator", "--old", "#old", "--dom", str(dom), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "suggestions" in data


def test_generate_bug_jira(tmp_path, capsys):
    rc = main(["generate-bug", str(_ctx_file(tmp_path)), "--format", "jira"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["fields"]["issuetype"]["name"] == "Bug"


def test_generate_bug_export_all(tmp_path, capsys):
    out_dir = tmp_path / "bug"
    rc = main(["generate-bug", str(_ctx_file(tmp_path)), "--out", str(out_dir)])
    assert rc == 0
    assert (out_dir / "bug.md").exists()
    assert (out_dir / "jira.json").exists()
