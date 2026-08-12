---
name: aiqa-sdk-skill
description: >-
  Guide for working inside the AIQA (multi-framework-tc-failure-ai-analyzer)
  codebase — a framework-agnostic AI failure-analysis SDK. Read this before
  adding an adapter, a reporter, an LLM provider, or extending the analysis
  engine, so changes match the existing architecture and conventions.
---

# AIQA SDK — Codebase Skill

This skill describes **how this repository is wired together** so a coding agent
can extend it (add an adapter, a reporter, an LLM provider, or an analysis rule)
while matching the existing conventions. It is a map of the codebase, not a
tutorial.

## What this project is

`aiqa` (installed as **`multi-framework-tc-failure-ai-analyzer`**, imported as
**`aiqa`**) is a **framework-agnostic AI failure-analysis SDK**. It turns a
failing test from *any* automation stack into an evidence-grounded root cause,
confidence score, owning team, fix recommendation, and tracker-ready bug report —
then aggregates runs into a Quality Intelligence dashboard.

The single, sacred architecture (dependencies point one direction only):

```
Adapters  →  FailureContext  →  AI Analysis Engine  →  AnalysisResult  →  Reporters
```

The **core has zero framework and zero application knowledge**. Framework code
lives only in adapters and is lazy-imported.

## Directory map

```
├── aiqa/                       # the SDK (this is the product)
│   ├── core/                   # pure domain: models + interfaces (stdlib only)
│   │   ├── models.py           #   FailureContext, AnalysisResult, BugReport, enums
│   │   └── interfaces.py       #   Analyzer, FrameworkAdapter, Reporter, LLMProvider, SimilarityIndex
│   ├── adapters/               # the ONLY layer that knows a framework
│   │   ├── playwright.py       #   PlaywrightAdapter + PlaywrightEventRecorder
│   │   ├── selenium.py         #   SeleniumAdapter
│   │   ├── robotframework.py   #   RobotFrameworkAdapter
│   │   ├── pytest_adapter.py   #   PytestAdapter
│   │   └── generic.py          #   GenericAdapter (dict | JSON str | path)
│   ├── analysis/               # FailureAnalyzer: heuristics + optional LLM + RAG
│   │   ├── analyzer.py         #   analyze(context) -> AnalysisResult
│   │   ├── classifier.py       #   FailureClassifier (category · owner · risk)
│   │   └── reasoning.py        #   ConfidenceReasoningBuilder (explainability)
│   ├── healing/                # AI locator healing (LocatorHealingEngine, ranker)
│   ├── reporting/              # reporters (md/json/html/console) + BugReportBuilder
│   │   ├── bug/                #   BugGenerationEngine + BugExporter (Jira/Azure/GitHub/Linear)
│   │   └── portal/             #   QualityPortal: multi-run history dashboard
│   ├── cli.py                  # `aiqa` CLI (classify · explain-failure · heal-locator · generate-bug)
│   └── config.py               # AiqaConfig (env-driven, all optional)
├── qa_ai_engine/               # backward-compatible pytest + Playwright plugin + assistant
│   ├── assistant/              #   QA AI Assistant (CLI + chat + tools, MCP-ready)
│   └── prompts loaded from prompts/
├── prompts/                    # external AI prompt templates ({{TOKEN}} injection)
├── examples/                   # runnable examples (generic, pytest, Playwright, Selenium, JSON)
├── tests/
│   ├── aiqa/                   # SDK unit tests (marker: sdk)
│   ├── ai/                     # qa_ai_engine unit tests (marker: ai)
│   ├── conftest.py             # opt-in QualityPortal + AI engine wiring (framework-agnostic)
│   └── test_ai_demo.py         # the single end-to-end demo (marker: demo)
├── utils/logger.py             # shared get_logger(name) factory
├── qa_ai.py                    # QA AI Assistant CLI entry point
├── pytest.ini                  # markers: demo, ai, sdk (offline, no browser/secrets)
└── requirements.txt
```

## The public API (import surface)

Everything a consumer needs is re-exported from the top-level package:

```python
from aiqa import (
    FailureAnalyzer, FailureContext, FailureContextBuilder,
    AnalysisResult, BugReport, render, analyze,
    QualityPortal, BugReportBuilder, get_reporter, available_formats,
)
from aiqa.adapters import (
    PlaywrightAdapter, SeleniumAdapter, RobotFrameworkAdapter,
    PytestAdapter, GenericAdapter,
)
```

The enterprise capabilities added in 3.2.0 are re-exported from the same
top-level package:

```python
from aiqa import (
    FailureClassifier, Classification, OwnerResolver, RiskLevel,
    ConfidenceReasoning,
    LocatorHealingEngine, LocatorRanker, HealingResult, LocatorSuggestion, heal_locator,
    BugGenerationEngine, BugExporter,
)
```

The engine's entire contract is one method:
`FailureAnalyzer.analyze(context: FailureContext) -> AnalysisResult`.

## Core domain (`aiqa/core`)

Pure, JSON-serialisable dataclasses, independent of every framework:

- `FailureContext` — the single input to the engine:
  `FailureMetadata` + `ExceptionInfo` + `Evidence` + `ExecutionContext`.
- `AnalysisResult` — `root_cause` (`RootCause.summary`, `.category`),
  `confidence` (`ConfidenceScore.value`), `severity`, `owner`, `evidence`,
  `recommendations` (`Recommendation[]`), `similar_failures` (`SimilarFailure[]`).
- `BugReport` — a tracker-ready report.

Build a context by hand with `FailureContextBuilder()` or from a dict with
`FailureContext.from_dict(...)`.

## How the analysis works (`aiqa/analysis`)

`FailureAnalyzer.analyze(context)`:

1. Retrieves similar past failures (RAG) — optional, pure-Python by default
   (`InMemoryIndex`; `NullIndex` to disable).
2. If an LLM provider is available, asks for an evidence-grounded JSON verdict;
   any failure transparently falls back to…
3. …a deterministic heuristic classifier (HTTP 5xx → Backend, 401 → Auth,
   403 → Authorization, locator/timeout/assertion signals, console errors, …).
4. Assigns a category, confidence, severity, owning team, and at least one fix
   recommendation.

Every claim is grounded in the collected evidence — the model cannot invent
signals that were not captured.

## Reporting (`aiqa/reporting`)

- Reporters consume an `AnalysisResult` only: `markdown`, `json`, `html`,
  `console`. Render via `render(result, fmt, context)` or `get_reporter(fmt)`.
- `BugReportBuilder().build(result, context)` → `BugReport`;
  `BugReportBuilder.to_markdown(bug)` renders it.
- `QualityPortal("reports")` aggregates runs into `reports/index.html` (quality
  score, release readiness, run comparison, flaky detection, trends) with zero
  extra dependencies.

## Conventions an agent must follow

1. **Never import a framework in the core.** No framework imports in
   `aiqa/core`, `aiqa/analysis`, or `aiqa/reporting`. Framework libraries
   (Playwright, Selenium, …) may only be imported **lazily, inside adapter
   methods** under `aiqa/adapters`.
2. **The engine accepts only a `FailureContext`** and returns an
   `AnalysisResult`. Do not pass framework objects into analysis.
3. **Reporters consume only an `AnalysisResult`** (plus an optional context).
4. **Add new framework support as a new adapter**, not by branching the core.
5. **Program to interfaces** in `aiqa/core/interfaces.py`
   (`FrameworkAdapter`, `Reporter`, `LLMProvider`, `SimilarityIndex`).
6. **Prompts are data** — never hardcode prompt strings; add/edit a
   `prompts/<name>.txt` using `{{TOKEN}}` placeholders.
7. **Ground everything** — heuristic and LLM outputs must reference real
   evidence; unsupported claims are filtered out.
8. **Mask secrets** before any evidence leaves the process (passwords, JWTs,
   bearer tokens, API keys, cookies).
9. **Keep the core dependency-free** (standard library only); optional SDKs are
   lazy-imported inside the layer that needs them.

## Recipes (how to automate common changes)

**Add a framework adapter**
1. Create `aiqa/adapters/<name>.py`; subclass `FrameworkAdapter`.
2. Lazy-import the framework library inside the method.
3. Return a fully-populated `FailureContext` from
   `collect_failure_context(...)`.
4. Re-export it from `aiqa/adapters/__init__.py` and add a unit test under
   `tests/aiqa/` marked `@pytest.mark.sdk`.

**Add a reporter**
1. Subclass `aiqa.core.interfaces.Reporter`, set `format`, implement `render`.
2. Decorate with `@register_reporter` (from `aiqa.reporting`).
3. Add a test asserting `get_reporter("<format>").render(result, ctx)` works.

**Add an LLM provider**
1. Implement `name`, `available()`, and `complete_json(prompt, system="")`.
2. Pass it in: `FailureAnalyzer(llm=MyProvider())`.
3. Keep the vendor SDK lazy-imported; never couple call sites to it.

**Add an analysis rule**: extend the heuristic classifier in
`aiqa/analysis/analyzer.py`, keep it evidence-grounded, and add a parametrized
case to `tests/aiqa/test_analyzer.py`.

## Running (Windows PowerShell)

Use the venv Python directly; chain commands with `;` (never `&&`).

```powershell
# The end-to-end demo (offline, no browser/secrets)
& ".venv/Scripts/python.exe" -m pytest tests/test_ai_demo.py -v -o addopts=""

# SDK + engine unit tests
& ".venv/Scripts/python.exe" -m pytest tests/aiqa tests/ai -m "sdk or ai" -o addopts=""

# Turn on the run-history dashboard, then open reports/index.html
$env:AIQA_PORTAL = "true"; & ".venv/Scripts/python.exe" -m pytest -o addopts=""
```

Markers (`pytest.ini`): `demo`, `ai`, `sdk` — all offline.

## Known project facts / gotchas

- Install name is `multi-framework-tc-failure-ai-analyzer`; import name is
  `aiqa`. Never change the import name.
- The SDK is **offline-first**: no API keys, no network, no extra dependencies
  by default. LLM providers are strictly opt-in via `aiqa/config.py` env vars.
- The `qa_ai_engine` package is the original pytest + Playwright plugin, kept for
  backward compatibility. Its optional imports of `utils.*` are guarded, so the
  SDK works standalone.
- The `QualityPortal` history is never wiped, so runs accumulate over time.
