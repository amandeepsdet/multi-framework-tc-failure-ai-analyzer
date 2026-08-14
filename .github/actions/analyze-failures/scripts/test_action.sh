#!/usr/bin/env bash
# Local smoke test for the AIQA GitHub Action (no GitHub required).
#
# Usage:  bash .github/actions/analyze-failures/scripts/test_action.sh
#
# Builds a sample JUnit report, runs the action entry point exactly as the
# runner would (via INPUT_* / GITHUB_* env vars), and prints the outputs, job
# summary and generated artifacts.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../../../.." && pwd)"
py="$repo_root/.venv/bin/python"
[ -x "$py" ] || py="python3"

work="$(mktemp -d)"
mkdir -p "$work/reports"
cat > "$work/reports/junit.xml" <<'XML'
<testsuite name="suite" tests="3">
<testcase classname="pkg" name="test_login"><failure message="AssertionError: expected 200 but got 500">trace</failure></testcase>
<testcase classname="pkg" name="test_checkout"><failure message="TimeoutError: navigation timeout">trace</failure></testcase>
<testcase classname="pkg" name="test_home"/>
</testsuite>
XML

export INPUT_REPORT_PATH="$work/reports"
export INPUT_OUTPUT_PATH="$work/out"
export INPUT_POST_COMMENT="false"
export INPUT_UPLOAD_ARTIFACT="true"
export GITHUB_OUTPUT="$work/gh_out"
export GITHUB_STEP_SUMMARY="$work/gh_sum"
export GITHUB_EVENT_NAME="push"
export GITHUB_REPOSITORY="acme/app"
export GITHUB_RUN_ID="99"
: > "$GITHUB_OUTPUT"
: > "$GITHUB_STEP_SUMMARY"

"$py" "$here/run.py"

echo; echo "=== ACTION OUTPUTS ==="; cat "$GITHUB_OUTPUT"
echo; echo "=== JOB SUMMARY ==="; cat "$GITHUB_STEP_SUMMARY"
echo; echo "=== GENERATED ARTIFACTS ==="; find "$work/out" -type f | sed "s|$work||"
