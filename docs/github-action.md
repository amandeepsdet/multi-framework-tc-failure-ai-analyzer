# GitHub Action — `analyze-failures`

Automatically analyze failed test artifacts with the AIQA SDK inside any GitHub
Actions workflow, and publish the results to the **Job Summary**, a **Pull
Request comment**, and an uploaded **artifact**. It runs **fully offline by
default** — no API keys, no external calls.

## Architecture

The action is an **integration layer**, not a second analysis engine. It reuses
the exact SDK pipeline the package already ships:

```text
Test Framework
      │
      ▼
GitHub Actions
      │
      ▼
AIQA Action  (this)
      │
      ▼
Artifact Discovery   (JUnit XML · JSON · Playwright · Robot)
      │
      ▼
Adapter              (GenericAdapter / FailureContextBuilder)
      │
      ▼
FailureContext
      │
      ▼
AI Analysis          (FailureAnalyzer + FailureClassifier)
      │
      ▼
Quality Intelligence (QualityPortal: readiness · history · knowledge base)
      │
      ▼
PR Comment + HTML Report + Artifact
```

## Installation

The action lives inside this repository, so consumers reference it by path and
version:

```yaml
uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
```

No separate install step is required — the action installs the pinned SDK
itself (and skips reinstalling if `aiqa` is already importable in the job).

## Minimal workflow

```yaml
name: Test + AI Analysis
on: [pull_request, push]

permissions:
  contents: read
  pull-requests: write

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest --junitxml=reports/junit.xml
        continue-on-error: true
      - name: AI Failure Analysis
        if: always()
        uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
        with:
          report-path: reports/
          framework: pytest
          post-comment: true
          upload-artifact: true
```

### Why `if: always()`?

When a test step fails, the job is marked failed and subsequent steps are
skipped by default. `if: always()` forces the analysis to run **because** the
tests failed — precisely when triage is needed. Pair it with
`continue-on-error: true` on the test step (or run the analysis in a later job)
so the original failure is still visible.

## Per-framework examples

### pytest

```yaml
- run: pytest --junitxml=reports/junit.xml
  continue-on-error: true
- if: always()
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/, framework: pytest }
```

### Playwright

```yaml
- run: npx playwright test --reporter=junit,json
  continue-on-error: true
  env: { PLAYWRIGHT_JUNIT_OUTPUT_NAME: reports/junit.xml }
- if: always()
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/, framework: playwright }
```

### Selenium (via JUnit output)

```yaml
- run: pytest tests/selenium --junitxml=reports/junit.xml   # or your runner's xUnit output
  continue-on-error: true
- if: always()
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/, framework: selenium }
```

### Robot Framework

```yaml
- run: robot --outputdir reports tests/    # produces reports/output.xml
  continue-on-error: true
- if: always()
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/, framework: robotframework }
```

### Generic JSON (Cypress, REST Assured, JUnit, CI, …)

Emit one or more serialized `FailureContext` JSON documents (or a `{ "failures": [...] }`
array) and point the action at the directory:

```yaml
- if: always()
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/, framework: generic }
```

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `report-path` | `reports/` | Directory (or file) containing test artifacts. |
| `framework` | `auto` | `auto` \| `pytest` \| `playwright` \| `selenium` \| `robotframework` \| `generic`. |
| `output-path` | `aiqa-report/` | Where the AIQA report + artifacts are written. |
| `fail-on-error` | `false` | Fail the step when failures are found (quality gate). |
| `post-comment` | `true` | Create/update one AI summary comment on the PR. |
| `upload-artifact` | `true` | Upload the complete report as a build artifact. |
| `artifact-name` | `aiqa-failure-analysis` | Name of the uploaded artifact. |
| `llm-provider` | `none` | Optional LLM provider (`none` \| `openai`). |
| `llm-api-key` | `''` | API key for the LLM provider. Never logged. |
| `analysis-mode` | `auto` | `auto` \| `offline` \| `llm`. |
| `github-token` | `${{ github.token }}` | Token used to post PR comments. |

## Outputs

| Output | Description |
|--------|-------------|
| `report-path` | Path to the generated AIQA report directory. |
| `report-url` | URL of the workflow run hosting the analysis. |
| `artifact-name` | Name of the uploaded artifact. |
| `failure-count` | Number of analyzed failures. |
| `failure-category` | The most common failure category. |
| `overall-status` | Release readiness: `READY` \| `AT_RISK` \| `NOT_READY`. |
| `quality-score` | Quality score 0–100. |

```yaml
- id: aiqa
  uses: amandeepsdet/multi-framework-tc-failure-ai-analyzer/.github/actions/analyze-failures@v1
  with: { report-path: reports/ }
- run: |
    echo "Readiness: ${{ steps.aiqa.outputs.overall-status }}"
    echo "Failures:  ${{ steps.aiqa.outputs.failure-count }}"
```

## PR comments

When `post-comment: true` and the workflow runs for a Pull Request, the action
creates a single concise summary comment and **updates it in place** on every
re-run (it never spams duplicates). It finds its own comment via a stable
marker: `<!-- aiqa-failure-analysis -->`.

The comment includes status, test counts, AI classification, top root cause,
confidence, suggested fix, and the split of **new** vs **known/recurring**
failures, plus links to the report and artifact.

## GitHub Step Summary

The action always writes a rich Job Summary (`$GITHUB_STEP_SUMMARY`) with test
statistics, failure classification, root cause, confidence, suggested fix,
release readiness, grouped failures, and the report location — so you understand
the result without opening the HTML report.

## Artifact upload

With `upload-artifact: true` the complete report is uploaded via
`actions/upload-artifact` under `aiqa-failure-analysis` (configurable). It
contains the QualityPortal `index.html` dashboard, the per-run `ai_report.html`,
and the supporting `report.json` / `report.md` / evidence, plus a stable
`aiqa-report.html` copy at the output root.

## LLM configuration

Offline heuristics are the default. To upgrade to an LLM, provide a provider and
a key **via secrets**:

```yaml
with:
  llm-provider: openai
  llm-api-key: ${{ secrets.OPENAI_API_KEY }}
  analysis-mode: llm
```

Evidence is sent to an external model **only** when both are set. Set
`analysis-mode: offline` to guarantee no external calls regardless of other
inputs.

## Offline mode

The default. No API keys, no network, negligible overhead — a deterministic
heuristic classifier, a pure-Python similarity index, and local JSON history.

## Permissions

```yaml
permissions:
  contents: read
  pull-requests: write   # only for post-comment: true
```

The action uses the workflow `GITHUB_TOKEN`; no PAT is required.

## Security

- Test output, stack traces, test names, and AI responses are **untrusted** —
  nothing found in them is ever executed.
- `GITHUB_TOKEN`, LLM keys, and common token shapes are masked from logs,
  summaries, PR comments and JSON.
- Evidence never leaves the runner unless an LLM is explicitly configured.
- Existing SDK evidence truncation/sanitization is reused; large logs are not
  sent blindly.

## Failure behavior

| Situation | Behavior |
|-----------|----------|
| Tests failed + analysis succeeded | Publish analysis; original test failure stays visible. Exit 0 (unless `fail-on-error`). |
| Tests passed, no failures | Publish a concise success summary. Exit 0. |
| Tests failed + analysis failed | Publish the analysis-failure reason + available artifacts. Exit 0 (unless `fail-on-error`). |
| Infrastructure failure (bad inputs, cannot import SDK) | Exit non-zero. |

Analysis is **non-blocking by default**.

## Quality gate

```yaml
with:
  fail-on-error: true    # fail the step when failures are detected
```

Future gates (planned): `min-confidence`, `max-critical-failures`,
`release-readiness`. The default never blocks unexpectedly.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Analysis step didn't run | Add `if: always()` and `continue-on-error: true` on the test step. |
| No PR comment | Ensure `permissions: pull-requests: write` and the event is `pull_request`. |
| "No test artifacts found" | Check `report-path` points at the directory your runner writes (e.g. `reports/`). |
| Wrong framework detected | Set `framework:` explicitly instead of `auto`. |
| Want zero external calls | Set `analysis-mode: offline`. |

## Versioning

Pin to a major tag: `@v1`. Future minor/major tags (`@v1.1`, `@v2`) preserve
`v1` compatibility within the major line. See the release strategy in the
repository README.
