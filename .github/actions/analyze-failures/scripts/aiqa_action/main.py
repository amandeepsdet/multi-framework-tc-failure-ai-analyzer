"""Entry point that orchestrates discovery -> analysis -> publish.

Failure-mode policy (default is non-blocking):

* **Tests failed + analysis succeeded** — publish analysis; exit 0 unless
  ``fail-on-error`` is set.
* **No failures** — publish a concise success summary; exit 0.
* **Tests failed + analysis failed** — publish the analysis-failure reason and
  whatever artifacts exist; exit 0 unless ``fail-on-error``.
* **Infrastructure failure** (bad inputs, cannot import SDK) — exit non-zero.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from . import analysis as analysis_mod
from . import discovery as discovery_mod
from . import github as gh
from . import render as render_mod
from .grouping import group_failures
from .inputs import load_inputs
from .masking import default_masker


def _log(msg: str) -> None:
    print(f"[aiqa] {msg}", flush=True)


def _build_report_url(env: Mapping[str, str]) -> str:
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo = env.get("GITHUB_REPOSITORY", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    if repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def run(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    inputs = load_inputs(env)
    masker = default_masker(inputs.llm_api_key)

    for w in inputs.warnings:
        _log(f"warning: {w}")

    # ---- Discovery ------------------------------------------------------- #
    discovery = discovery_mod.discover_failures(inputs.report_path, inputs.framework)
    for w in discovery.warnings:
        _log(f"warning: {masker.mask(w)}")

    reports_dir = str(Path(inputs.output_path) / "reports")
    report_url = _build_report_url(env)

    # No artifacts at all -> nothing to do, but not an error.
    if not discovery.artifacts_found:
        _log(f"No test artifacts found under '{inputs.report_path}'.")
        _publish_empty(inputs, discovery, reports_dir, env)
        return 0

    # Artifacts present but no failures -> success summary.
    if not discovery.has_failures:
        _log(f"No failures detected ({discovery.passed}/{discovery.total} passed).")
        outcome = _safe_analyze(inputs, discovery, reports_dir, report_url, masker)
        _publish(inputs, outcome, discovery, reports_dir, report_url, masker, env)
        return 0

    # ---- Analysis -------------------------------------------------------- #
    _log(
        f"Analyzing {len(discovery.contexts)} failure(s) "
        f"[framework={discovery.detected_framework}, mode={inputs.analysis_mode}]"
    )
    outcome = _safe_analyze(inputs, discovery, reports_dir, report_url, masker)
    _publish(inputs, outcome, discovery, reports_dir, report_url, masker, env)

    if inputs.fail_on_error and (outcome.run is None or outcome.run.failed > 0):
        return 1
    return 0


def _safe_analyze(inputs, discovery, reports_dir, report_url, masker):
    output_html = str(Path(inputs.output_path) / "aiqa-report.html")
    try:
        return analysis_mod.run_analysis(
            discovery.contexts,
            passed=discovery.passed,
            skipped=discovery.skipped,
            framework=discovery.detected_framework,
            environment=os.getenv("GITHUB_REF_NAME", "ci"),
            reports_dir=reports_dir,
            commit=os.getenv("GITHUB_SHA", ""),
            use_llm=inputs.use_llm,
            llm_provider=inputs.llm_provider,
            llm_api_key=inputs.llm_api_key,
            output_html=output_html,
        )
    except Exception as exc:  # analysis failure must not crash the action
        _log(f"error: analysis failed: {masker.mask(type(exc).__name__ + ': ' + str(exc))}")
        return analysis_mod.AnalysisOutcome(warnings=[f"Analysis failed: {type(exc).__name__}"])


def _publish(inputs, outcome, discovery, reports_dir, report_url, masker, env) -> None:
    groups = group_failures(outcome.run)
    warnings = list(discovery.warnings) + list(outcome.warnings)

    # Step summary.
    summary = render_mod.build_step_summary(
        outcome.run,
        groups=groups,
        memories=outcome.memories,
        report_path=reports_dir,
        warnings=warnings,
    )
    gh.write_step_summary(masker.mask(summary), env.get("GITHUB_STEP_SUMMARY"))

    # Outputs.
    outputs = render_mod.build_outputs(
        outcome.run,
        report_path=reports_dir,
        report_url=report_url,
        artifact_name=inputs.artifact_name if inputs.upload_artifact else "",
    )
    gh.write_outputs(outputs, env.get("GITHUB_OUTPUT"))

    # PR comment (only for pull_request events, only when requested).
    if inputs.post_comment:
        _maybe_comment(inputs, outcome, groups, report_url, masker, env)


def _maybe_comment(inputs, outcome, groups, report_url, masker, env) -> None:
    event = env.get("GITHUB_EVENT_NAME", "")
    if not event.startswith("pull_request"):
        _log("Not a pull_request event; skipping PR comment.")
        return
    token = env.get("GITHUB_TOKEN", "")
    if not token:
        _log("No GITHUB_TOKEN available; skipping PR comment.")
        return
    pr = gh.pr_number_from_event(env.get("GITHUB_EVENT_PATH"))
    if not pr:
        _log("Could not resolve PR number; skipping PR comment.")
        return
    body = render_mod.build_pr_comment(
        outcome.run,
        groups=groups,
        memories=outcome.memories,
        report_url=report_url,
    )
    ok, action = gh.upsert_pr_comment(
        masker.mask(body),
        token=token,
        repo=env.get("GITHUB_REPOSITORY", ""),
        pr_number=pr,
        api_url=env.get("GITHUB_API_URL", "https://api.github.com"),
    )
    _log(f"PR comment {action}: {'ok' if ok else 'failed'}")


def _publish_empty(inputs, discovery, reports_dir, env) -> None:
    summary = render_mod.build_step_summary(
        None, warnings=discovery.warnings, report_path=reports_dir
    )
    gh.write_step_summary(summary, env.get("GITHUB_STEP_SUMMARY"))
    gh.write_outputs(
        render_mod.build_outputs(None, report_path=reports_dir, artifact_name=inputs.artifact_name)
        | {"overall-status": "NO_ARTIFACTS", "failure-count": "0"},
        env.get("GITHUB_OUTPUT"),
    )


def main() -> int:
    try:
        return run()
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except Exception as exc:  # infrastructure failure
        print(f"[aiqa] fatal: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
