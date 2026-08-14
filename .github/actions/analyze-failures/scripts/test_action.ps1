# Local smoke test for the AIQA GitHub Action (no GitHub required).
#
# Usage:  pwsh -File .github/actions/analyze-failures/scripts/test_action.ps1
#
# Builds a sample JUnit report, runs the action entry point exactly as the
# runner would (via INPUT_* / GITHUB_* env vars), and prints the outputs,
# job summary and generated artifacts.

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
$py = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$work = Join-Path ([System.IO.Path]::GetTempPath()) "aiqa_action_smoke"
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path (Join-Path $work "reports") -Force | Out-Null

$junit = @"
<testsuite name="suite" tests="3">
<testcase classname="pkg" name="test_login"><failure message="AssertionError: expected 200 but got 500">trace</failure></testcase>
<testcase classname="pkg" name="test_checkout"><failure message="TimeoutError: navigation timeout">trace</failure></testcase>
<testcase classname="pkg" name="test_home"/>
</testsuite>
"@
Set-Content -Path (Join-Path $work "reports\junit.xml") -Value $junit -Encoding utf8

$env:INPUT_REPORT_PATH   = Join-Path $work "reports"
$env:INPUT_OUTPUT_PATH   = Join-Path $work "out"
$env:INPUT_POST_COMMENT  = "false"
$env:INPUT_UPLOAD_ARTIFACT = "true"
$env:GITHUB_OUTPUT       = Join-Path $work "gh_out"
$env:GITHUB_STEP_SUMMARY = Join-Path $work "gh_sum"
$env:GITHUB_EVENT_NAME   = "push"
$env:GITHUB_REPOSITORY   = "acme/app"
$env:GITHUB_RUN_ID       = "99"
Set-Content -Path $env:GITHUB_OUTPUT -Value "" -Encoding utf8
Set-Content -Path $env:GITHUB_STEP_SUMMARY -Value "" -Encoding utf8

& $py (Join-Path $PSScriptRoot "run.py")

Write-Host "`n=== ACTION OUTPUTS ===" -ForegroundColor Cyan
Get-Content $env:GITHUB_OUTPUT
Write-Host "`n=== JOB SUMMARY ===" -ForegroundColor Cyan
Get-Content $env:GITHUB_STEP_SUMMARY
Write-Host "`n=== GENERATED ARTIFACTS ===" -ForegroundColor Cyan
Get-ChildItem -Recurse (Join-Path $work "out") | ForEach-Object { $_.FullName.Replace($work, "") }
