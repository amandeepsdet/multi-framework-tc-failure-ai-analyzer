"""Tests for the AIQA GitHub Action orchestration (offline, no network).

Covers the 18 required scenarios. The action reuses the SDK pipeline, so these
tests focus on orchestration: input parsing, artifact discovery, analysis
wiring, rendering, GitHub side-effects, secret masking, and failure modes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiqa_action import discovery as discovery_mod
from aiqa_action import github as gh
from aiqa_action import main as main_mod
from aiqa_action import render as render_mod
from aiqa_action.grouping import group_failures
from aiqa_action.inputs import load_inputs
from aiqa_action.masking import SecretMasker


# --------------------------------------------------------------------------- #
# Artifact helpers
# --------------------------------------------------------------------------- #
def _junit(path: Path, cases: list[tuple[str, str | None]]) -> Path:
    """cases: list of (name, failure_message|None)."""
    body = ['<testsuite name="suite" tests="{}">'.format(len(cases))]
    for name, msg in cases:
        if msg is None:
            body.append(f'<testcase classname="pkg" name="{name}"/>')
        else:
            body.append(
                f'<testcase classname="pkg" name="{name}">'
                f'<failure message="{msg}">Traceback here</failure></testcase>'
            )
    body.append("</testsuite>")
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def _base_env(tmp_path: Path, **over: str) -> dict[str, str]:
    out = tmp_path / "gh_output"
    summ = tmp_path / "gh_summary"
    out.write_text("", encoding="utf-8")
    summ.write_text("", encoding="utf-8")
    env = {
        "INPUT_REPORT_PATH": str(tmp_path / "reports"),
        "INPUT_OUTPUT_PATH": str(tmp_path / "aiqa-report"),
        "INPUT_POST_COMMENT": "false",
        "INPUT_UPLOAD_ARTIFACT": "true",
        "GITHUB_OUTPUT": str(out),
        "GITHUB_STEP_SUMMARY": str(summ),
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REPOSITORY": "acme/app",
        "GITHUB_RUN_ID": "42",
    }
    env.update(over)
    return env


def _read_outputs(env: dict[str, str]) -> dict[str, str]:
    text = Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


# --------------------------------------------------------------------------- #
# 1. Input parsing
# --------------------------------------------------------------------------- #
def test_input_parsing_defaults_and_overrides():
    inputs = load_inputs({})
    assert inputs.report_path == "reports/"
    assert inputs.framework == "auto"
    assert inputs.post_comment is True
    assert inputs.fail_on_error is False

    inputs = load_inputs(
        {"INPUT_REPORT_PATH": "out/", "INPUT_FAIL_ON_ERROR": "true", "INPUT_POST_COMMENT": "no"}
    )
    assert inputs.report_path == "out/"
    assert inputs.fail_on_error is True
    assert inputs.post_comment is False


# --------------------------------------------------------------------------- #
# 2. Missing report directory
# --------------------------------------------------------------------------- #
def test_missing_report_directory(tmp_path):
    result = discovery_mod.discover_failures(tmp_path / "nope", "auto")
    assert not result.artifacts_found
    assert result.contexts == []
    assert any("does not exist" in w for w in result.warnings)


# --------------------------------------------------------------------------- #
# 3. Empty report directory
# --------------------------------------------------------------------------- #
def test_empty_report_directory(tmp_path):
    (tmp_path / "reports").mkdir()
    result = discovery_mod.discover_failures(tmp_path / "reports", "auto")
    assert not result.artifacts_found
    assert not result.has_failures


# --------------------------------------------------------------------------- #
# 4. Test failures discovered and analyzed end-to-end
# --------------------------------------------------------------------------- #
def test_run_with_failures_end_to_end(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _junit(reports / "junit.xml", [("test_login", "AssertionError: expected 200 but got 500"),
                                    ("test_ok", None)])
    env = _base_env(tmp_path)
    rc = main_mod.run(env)
    assert rc == 0
    outputs = _read_outputs(env)
    assert outputs["failure-count"] == "1"
    assert outputs["overall-status"] in {"READY", "AT_RISK", "NOT_READY"}
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert "AIQA Analysis" in summary


# --------------------------------------------------------------------------- #
# 5. Successful run (no failures) -> success summary, exit 0
# --------------------------------------------------------------------------- #
def test_successful_run_summary(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _junit(reports / "junit.xml", [("test_a", None), ("test_b", None)])
    env = _base_env(tmp_path)
    rc = main_mod.run(env)
    assert rc == 0
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert "No failures" in summary


# --------------------------------------------------------------------------- #
# 6. Multiple failures
# --------------------------------------------------------------------------- #
def test_multiple_failures(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _junit(
        reports / "junit.xml",
        [
            ("test_a", "AssertionError: boom"),
            ("test_b", "TimeoutError: timed out"),
            ("test_c", "ValueError: bad"),
        ],
    )
    result = discovery_mod.discover_failures(reports, "auto")
    assert len(result.contexts) == 3
    assert result.total == 3


# --------------------------------------------------------------------------- #
# 7. Duplicate failure grouping
# --------------------------------------------------------------------------- #
def test_duplicate_failure_grouping():
    from aiqa import FailureAnalyzer, FailureContextBuilder
    from aiqa.reporting.portal.models import ExecutionRun, RunFailure

    analyzer = FailureAnalyzer()
    run = ExecutionRun()
    for i in range(3):
        ctx = (
            FailureContextBuilder()
            .with_test(f"test_auth_{i}")
            .with_network([{"method": "POST", "url": "/api", "status": 401}])
            .build()
        )
        result = analyzer.analyze(ctx)
        run.failures.append(RunFailure.from_analysis(result, ctx))
    groups = group_failures(run)
    # All three share the same category/root cause -> one group of 3.
    assert groups[0].count == 3


# --------------------------------------------------------------------------- #
# 8 & 9. PR comment creation and update
# --------------------------------------------------------------------------- #
class _FakeGitHub:
    def __init__(self, existing: list[dict] | None = None):
        self.existing = existing or []
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        assert headers["Authorization"].startswith("Bearer ")
        if method == "GET":
            return 200, self.existing
        return 201 if method == "POST" else 200, {"id": 1}


def test_pr_comment_created():
    fake = _FakeGitHub(existing=[])
    ok, action = gh.upsert_pr_comment(
        "body", token="t", repo="acme/app", pr_number=7, http=fake
    )
    assert ok and action == "created"
    assert any(m == "POST" for m, _ in fake.calls)


def test_pr_comment_updated_not_duplicated():
    marker = render_mod.COMMENT_MARKER
    fake = _FakeGitHub(existing=[{"id": 99, "body": f"{marker}\nold"}])
    ok, action = gh.upsert_pr_comment(
        "new body", token="t", repo="acme/app", pr_number=7, http=fake
    )
    assert ok and action == "updated"
    assert any(m == "PATCH" and "99" in url for m, url in fake.calls)
    assert not any(m == "POST" for m, _ in fake.calls)


def test_find_existing_comment_marker():
    comments = [{"id": 1, "body": "hi"}, {"id": 2, "body": render_mod.COMMENT_MARKER}]
    assert gh.find_existing_comment(comments) == 2


# --------------------------------------------------------------------------- #
# 10. Artifact path / outputs generation
# --------------------------------------------------------------------------- #
def test_output_generation_when_no_run():
    outputs = render_mod.build_outputs(None, report_path="aiqa/reports", artifact_name="aiqa")
    assert outputs["overall-status"] == "ANALYSIS_FAILED"
    assert outputs["artifact-name"] == "aiqa"
    assert outputs["failure-count"] == "0"


# --------------------------------------------------------------------------- #
# 11. GitHub output file writing
# --------------------------------------------------------------------------- #
def test_write_outputs_file(tmp_path):
    out = tmp_path / "out"
    gh.write_outputs({"a": "1", "multi": "line1\nline2"}, str(out))
    text = out.read_text(encoding="utf-8")
    assert "a=1" in text
    assert "multi=line1 line2" in text  # newlines collapsed to keep key=value valid


# --------------------------------------------------------------------------- #
# 12. Missing GITHUB_TOKEN -> comment skipped, no crash
# --------------------------------------------------------------------------- #
def test_missing_github_token_skips_comment():
    ok, action = gh.upsert_pr_comment("b", token="", repo="acme/app", pr_number=1)
    assert not ok and action == "missing-token"


# --------------------------------------------------------------------------- #
# 13. Offline mode (default) -> use_llm False
# --------------------------------------------------------------------------- #
def test_offline_mode_default():
    inputs = load_inputs({"INPUT_ANALYSIS_MODE": "offline", "INPUT_LLM_PROVIDER": "openai",
                          "INPUT_LLM_API_KEY": "sk-secret"})
    assert inputs.use_llm is False


# --------------------------------------------------------------------------- #
# 14. External LLM mode -> use_llm True only when provider + key set
# --------------------------------------------------------------------------- #
def test_llm_mode_requires_provider_and_key():
    assert load_inputs({"INPUT_LLM_PROVIDER": "openai"}).use_llm is False
    assert load_inputs(
        {"INPUT_LLM_PROVIDER": "openai", "INPUT_LLM_API_KEY": "sk-x"}
    ).use_llm is True


# --------------------------------------------------------------------------- #
# 15. Secret masking
# --------------------------------------------------------------------------- #
def test_secret_masking():
    masker = SecretMasker(["sk-supersecretvalue123456"])
    text = "key=sk-supersecretvalue123456 token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    masked = masker.mask(text)
    assert "sk-supersecretvalue123456" not in masked
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in masked
    assert "***" in masked


# --------------------------------------------------------------------------- #
# 16. Analysis failure -> action still exits 0 (non-blocking), status recorded
# --------------------------------------------------------------------------- #
def test_analysis_failure_is_non_blocking(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    _junit(reports / "junit.xml", [("test_x", "Error: nope")])

    def _boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(main_mod.analysis_mod, "run_analysis", _boom)
    env = _base_env(tmp_path)
    rc = main_mod.run(env)
    assert rc == 0
    outputs = _read_outputs(env)
    assert outputs["overall-status"] == "ANALYSIS_FAILED"


def test_fail_on_error_blocks_when_requested(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _junit(reports / "junit.xml", [("test_x", "AssertionError: boom")])
    env = _base_env(tmp_path, INPUT_FAIL_ON_ERROR="true")
    rc = main_mod.run(env)
    assert rc == 1


# --------------------------------------------------------------------------- #
# 17. Unsupported framework -> falls back to auto with a warning
# --------------------------------------------------------------------------- #
def test_unsupported_framework_falls_back():
    inputs = load_inputs({"INPUT_FRAMEWORK": "karate"})
    assert inputs.framework == "auto"
    assert any("karate" in w for w in inputs.warnings)


# --------------------------------------------------------------------------- #
# 18. Automatic framework detection
# --------------------------------------------------------------------------- #
def test_auto_framework_detection_robot(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "output.xml").write_text(
        '<robot><suite><test name="T1"><status status="FAIL">Keyword X failed</status>'
        "</test></suite></robot>",
        encoding="utf-8",
    )
    result = discovery_mod.discover_failures(reports, "auto")
    assert result.detected_framework == "robotframework"
    assert len(result.contexts) == 1


def test_auto_framework_detection_generic_json(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {
        "metadata": {"test_name": "checkout::test_pay", "framework": "cypress"},
        "exception": {"type": "AssertionError", "message": "HTTP 500"},
        "evidence": {"network": [{"method": "POST", "url": "/api/pay", "status": 500}]},
    }
    (reports / "failure.json").write_text(json.dumps(payload), encoding="utf-8")
    result = discovery_mod.discover_failures(reports, "auto")
    assert result.detected_framework == "generic"
    assert len(result.contexts) == 1
    assert result.contexts[0].test_name == "checkout::test_pay"
