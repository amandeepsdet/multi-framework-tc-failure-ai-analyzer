# AIQA — an AI-powered Quality Engineering SDK

**Turn a failing test from _any_ automation framework into an evidence-grounded
root-cause analysis, a confidence score, an owning team, and a tracker-ready bug
report.**

AIQA is **not** a Playwright tool. Its core understands only **failures,
evidence, context, analysis, and reports** — never a specific application,
framework, or DOM. Framework knowledge lives entirely in swappable **adapters**,
so the same engine works with Playwright, Selenium, Cypress, Robot Framework,
Appium, Requests, REST Assured, JUnit, NUnit, TestNG, pytest — or anything that
can emit JSON.

It runs **fully offline with zero API keys** (deterministic heuristic engine +
pure-Python similarity search) and upgrades transparently to an LLM when you
configure one.

> Install name: `multi-framework-tc-failure-ai-analyzer` · Import name: `aiqa`

> **Renamed package.** This project was formerly published as
> `playwright-tc-failure-ai-analyzer`. It is now
> **`multi-framework-tc-failure-ai-analyzer`** to reflect its framework-agnostic,
> adapter-based design. Future releases ship only under the new name — see the
> [Migration Guide](https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/blob/main/docs/MIGRATION.md).

---

## Architecture

Dependencies point in one direction only. The core domain depends on nothing;
everything depends on the core.

```
   Adapters                 (framework-specific: Playwright, Selenium, pytest…)
      │  produce
      ▼
   FailureContext           ← Core Domain (pure, framework-agnostic models)
      │  consumed by
      ▼
   AI Analysis Engine       analyze(context) -> AnalysisResult   (never imports a framework)
      │  produces
      ▼
   Reporting                (Markdown · JSON · HTML · Console · your own)
      │
      ▼
   Output
```

| Layer | Package | Knows a framework? | Depends on |
|-------|---------|--------------------|------------|
| Adapters | `aiqa.adapters` | **Yes** (only here) | core |
| Core domain | `aiqa.core` | No | standard library only |
| AI engine | `aiqa.analysis` | No | core (+ optional LLM SDK, lazy) |
| Reporting | `aiqa.reporting` | No | core |

The engine's entire contract is one method:
`analyze(context: FailureContext) -> AnalysisResult`.

---

## Install

```bash
pip install multi-framework-tc-failure-ai-analyzer            # core SDK (offline)
pip install "multi-framework-tc-failure-ai-analyzer[openai]"  # + LLM analysis
```

## Quick start

```python
from aiqa import FailureAnalyzer, FailureContext, render

context = FailureContext.from_dict({
    "metadata": {"test_name": "checkout::test_pay", "framework": "cypress"},
    "exception": {"type": "AssertionError", "message": "server returned HTTP 500"},
    "evidence": {"network": [{"method": "POST", "url": "/api/pay", "status": 500}]},
})

result = FailureAnalyzer().analyze(context)          # offline by default
print(render(result, "markdown", context))
print(result.category.value, result.confidence.value, result.owner)
```

## Using adapters

Every adapter exposes `collect_failure_context(...)` and returns a
`FailureContext`.

**Playwright**
```python
from aiqa import FailureAnalyzer, render
from aiqa.adapters import PlaywrightAdapter, PlaywrightEventRecorder

recorder = PlaywrightEventRecorder(page)   # at test start (captures console/network)
# ... on failure:
context = PlaywrightAdapter(page=page, recorder=recorder).collect_failure_context(
    exc, test_name="login::test_submit", screenshot="fail.png", browser="chromium",
)
print(render(FailureAnalyzer().analyze(context), "console", context))
```

**Selenium**
```python
from aiqa.adapters import SeleniumAdapter
context = SeleniumAdapter(driver=driver).collect_failure_context(exc, test_name="orders::checkout")
```

**pytest** (any test type — UI, API, unit)
```python
from aiqa.adapters import PytestAdapter
# in conftest.py pytest_runtest_makereport:
context = PytestAdapter().collect_failure_context(item=item, call=call, report=report)
```

**Robot Framework**
```python
from aiqa.adapters import RobotFrameworkAdapter
context = RobotFrameworkAdapter().collect_failure_context(
    test_name="Login Works", message="Element not visible", suite="Login")
```

**Anything (JSON)** — Cypress, REST Assured, JUnit, NUnit, TestNG, CI scripts:
```python
from aiqa.adapters import GenericAdapter
context = GenericAdapter().collect_failure_context("failure.json")   # dict | JSON str | path
```

Runnable scripts live in [`examples/`](examples/).

---

## Core domain

Pure, JSON-serialisable dataclasses in `aiqa.core`, independent of every
framework:

- `FailureContext` — the single input to the engine, composed of:
  - `FailureMetadata` (test id/name, suite, framework, tags, timing, git commit)
  - `ExceptionInfo` (type, message, stacktrace)
  - `Evidence` (screenshot, DOM snapshot, console, network, API responses, logs,
    artifacts, and open-ended `custom` evidence)
  - `ExecutionContext` (environment, browser, OS, URL, timestamp, configuration)
- `AnalysisResult` — `RootCause`, `ConfidenceScore`, `Severity`, `owner`,
  `evidence`, `Recommendation[]`, `SimilarFailure[]`
- `BugReport` — a tracker-ready report

## AI analysis

`FailureAnalyzer.analyze(context)`:

1. Retrieves similar past failures (RAG) — optional, pure-Python by default.
2. If an LLM provider is available, asks for an evidence-grounded JSON verdict;
   any failure transparently falls back to…
3. …a deterministic heuristic classifier (HTTP 5xx → Backend, 401 → Auth,
   locator / timeout / assertion signals, console errors, …).
4. Assigns a category, confidence, severity, and owning team.

Every claim is grounded in the collected evidence — the model cannot invent
signals that were not captured.

## Reports

Reporters consume an `AnalysisResult` only. Built in: `markdown`, `json`,
`html`, `console`.

```python
from aiqa import get_reporter, available_formats
print(available_formats())                     # ['console', 'html', 'json', 'markdown']
html = get_reporter("html").render(result, context)
```

Bug reports:
```python
from aiqa.reporting import BugReportBuilder
bug = BugReportBuilder().build(result, context)
print(BugReportBuilder.to_markdown(bug))
```

---

## Extensibility

Every seam is an interface (`aiqa.core.interfaces`) — extend without touching
existing code.

**Custom LLM provider** — implement three members:
```python
class MyProvider:
    name = "my-llm"
    def available(self): return True
    def complete_json(self, prompt, system=""): return {...}

FailureAnalyzer(llm=MyProvider())
```

**Custom reporter** — subclass and register:
```python
from aiqa.core.interfaces import Reporter
from aiqa.reporting import register_reporter

@register_reporter
class SlackReporter(Reporter):
    format = "slack"
    def render(self, result, context=None): return f":rotating_light: {result.root_cause.summary}"
```

**Custom adapter** — subclass `FrameworkAdapter` and return a `FailureContext`.
**Custom similarity/RAG backend** — implement the `SimilarityIndex` protocol.

## Configuration (all optional, env-driven)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AIQA_PROVIDER` | `offline` | `offline` (heuristic) or `openai`. |
| `AIQA_MODEL` | `gpt-4o-mini` | Model name for the chosen provider. |
| `AIQA_API_KEY` | – | Key (falls back to `OPENAI_API_KEY`). |
| `AIQA_BASE_URL` | – | Custom/compatible endpoint (Azure, local, …). |
| `AIQA_ENABLE_HISTORY` | `false` | Persist a local similarity index. |
| `AIQA_BASE_DIR` | `.aiqa` | Where history is written. |

Offline mode requires **no keys and no extra dependencies**.

---

## Design guarantees

- The **core** has zero framework and zero application knowledge.
- The **engine** accepts only a `FailureContext` and never imports Playwright.
- **Reports** consume only an `AnalysisResult`.
- All framework logic is isolated in **adapters** (framework libs lazy-imported).
- Full type hints, SOLID boundaries, no circular dependencies, unit-testable.

## Also included: `qa_ai_engine` pytest plugin (backward-compatible)

The same distribution still ships the original auto-discovered pytest plugin for
pytest + Playwright projects, unchanged. Enable it with `AI_ENABLED=true` and
use `from qa_ai_engine import AIEngine`. New projects should prefer the
framework-agnostic `aiqa` SDK above.

## License

MIT © Aman Deep
