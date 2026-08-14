# AIQA Failure Analysis — GitHub Action

Analyze failed test artifacts from **any** framework with the
[AIQA SDK](https://pypi.org/project/multi-framework-tc-failure-ai-analyzer/) and
publish the results to the **Job Summary**, a **Pull Request comment**, and an
uploaded **artifact** — fully offline by default (no API keys required).

This is a **repository-local composite action**. It is *orchestration only*: it
discovers artifacts, feeds them through the existing SDK pipeline
(adapters → `FailureContext` → `FailureAnalyzer` → `QualityPortal` → reporters),
and publishes the result. It contains **no** analysis logic of its own.

```text
Test Framework → GitHub Actions → AIQA Action → Artifact Discovery → Adapter
   → FailureContext → AI Analysis → Quality Intelligence
   → PR Comment + HTML Report + Artifact
```

## Usage

```yaml
- name: AI Failure Analysis
  if: always()          # run even though the test step failed
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with:
    report-path: reports/
    framework: pytest
    post-comment: true
    upload-artifact: true
```

> **Why `if: always()`?** When tests fail, the failing step marks the job
> failed and, by default, later steps are skipped. `if: always()` forces the
> analysis to run *because* the tests failed — which is exactly when you want it.

### Minimum permissions

```yaml
permissions:
  contents: read
  pull-requests: write   # only needed for post-comment: true
```

The action uses the workflow `GITHUB_TOKEN` — no personal access token needed.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `report-path` | `reports/` | Directory (or file) containing test artifacts. |
| `framework` | `auto` | `auto` \| `pytest` \| `playwright` \| `selenium` \| `robotframework` \| `generic`. |
| `output-path` | `aiqa-report/` | Where the AIQA report + artifacts are written. |
| `fail-on-error` | `false` | Fail the step when failures are found (quality gate). Non-blocking by default. |
| `post-comment` | `true` | Create/update one AI summary comment on the PR. |
| `upload-artifact` | `true` | Upload the complete report as a build artifact. |
| `artifact-name` | `aiqa-failure-analysis` | Name of the uploaded artifact. |
| `llm-provider` | `none` | Optional LLM provider (`none` \| `openai`). Offline heuristics used when unset. |
| `llm-api-key` | `''` | API key for the LLM provider. **Never logged.** |
| `analysis-mode` | `auto` | `auto` \| `offline` \| `llm`. `offline` forces the zero-cost engine. |
| `github-token` | `${{ github.token }}` | Token used to post PR comments. |

## Outputs

| Output | Description |
|--------|-------------|
| `report-path` | Path to the generated AIQA report directory. |
| `report-url` | URL of the workflow run hosting the analysis. |
| `artifact-name` | Name of the uploaded artifact (empty when upload disabled). |
| `failure-count` | Number of analyzed failures. |
| `failure-category` | The most common failure category. |
| `overall-status` | Release readiness: `READY` \| `AT_RISK` \| `NOT_READY`. |
| `quality-score` | Quality score 0–100. |

```yaml
- id: aiqa
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/ }
- run: echo "Status ${{ steps.aiqa.outputs.overall-status }} (${{ steps.aiqa.outputs.failure-count }} failures)"
```

## Supported artifacts

JUnit / xUnit XML (universal — pytest, Selenium, Playwright, Robot `--xunit`),
generic **JSON** (a serialized `FailureContext` or a list of them), Playwright
`results.json`, and Robot Framework `output.xml`. Nearby screenshots, logs and
traces are associated with a failure on a best-effort basis. With
`framework: auto` the format is detected automatically.

## Security

- Uses `GITHUB_TOKEN`; never requires a PAT.
- Test output, stack traces, and AI responses are treated as **untrusted** — the
  action never executes anything found in them.
- `GITHUB_TOKEN` and LLM keys are masked from logs, summaries, comments and JSON.
- Offline by default: evidence is **only** sent to an external model when
  `llm-provider` + `llm-api-key` are explicitly set.

## Local testing

```powershell
pwsh -File .github/actions/analyze-failures/scripts/test_action.ps1
```
```bash
bash .github/actions/analyze-failures/scripts/test_action.sh
```

## Versioning

Pin to a major tag for stability: `@v1`. Future: `@v1.1`, `@v2`. `v1`
compatibility is preserved within the major line. See
[docs/github-action.md](../../../docs/github-action.md) for full documentation,
per-framework examples, and troubleshooting.
