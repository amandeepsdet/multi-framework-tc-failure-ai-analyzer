# About This Project

## AIQA — an AI-powered Quality Engineering SDK (published on PyPI)

The headline deliverable is **`aiqa`**, a **framework-agnostic SDK** that turns a
failing test from *any* automation stack — Playwright, Selenium, Cypress, Robot
Framework, Appium, Requests, REST Assured, JUnit, NUnit, TestNG, pytest, or
anything that can emit JSON — into an evidence-grounded **root cause**,
**confidence score**, **owning team**, and **tracker-ready bug report**. It runs
fully offline (deterministic heuristics + pure-Python similarity) and upgrades
transparently to an LLM when configured.

- **Install:** `pip install multi-framework-tc-failure-ai-analyzer` · **import:** `aiqa`
- **Architecture:** Adapters → `FailureContext` → AI Engine → `AnalysisResult` → Reporters.
  The core has **zero** framework and **zero** application knowledge; all
  framework logic lives in swappable adapters.
- **Quality Intelligence Platform:** `QualityPortal` aggregates every execution
  into a historical HTML dashboard — quality score, release readiness, trends,
  flaky detection, run comparison, and a knowledge base — with zero extra
  dependencies.
- **Docs:** [PACKAGE_README.md](PACKAGE_README.md) · runnable [`examples/`](examples/) · [Migration Guide](docs/MIGRATION.md).

---

## 1. What is this, in plain words?

Most test frameworks only tell you that a test **failed**. AIQA tells you **why
it failed, what broke, who should fix it, how confident it is, and how to fix
it** — then writes the bug report for you.

It plugs into whatever you already use to run tests. When a test fails, an
adapter captures the evidence, the AI engine investigates the failure like a
senior engineer would, and the result is rendered as a report and added to a
run-history dashboard.

---

## 2. The core idea

```
Adapters  →  FailureContext  →  AI Analysis Engine  →  AnalysisResult  →  Reporters
```

- **Adapters** — the only layer that knows a framework. Each one (Playwright,
  Selenium, Robot Framework, pytest, or the generic JSON adapter) produces a
  `FailureContext`.
- **`FailureContext`** — a pure, framework-agnostic snapshot of the failure:
  exception, assertion, screenshot, DOM, console logs, network calls, API
  responses, and metadata.
- **AI Analysis Engine** — accepts only a `FailureContext` and returns an
  `AnalysisResult`. It never imports a framework or an application.
- **`AnalysisResult`** — root cause, category, confidence, severity, owning team,
  grounded evidence, and a fix recommendation.
- **Reporters** — render an `AnalysisResult` as Markdown, JSON, HTML, or a
  console summary, build a tracker-ready bug report, or feed the `QualityPortal`
  run-history dashboard.

---

## 3. What the AI layer does on every failure

Normally a framework only says:

> ❌ FAIL — "Element not found"

AIQA instead answers:

> 🧠 **Root cause:** A backend service returned HTTP 500, so the page had no
> data to render.
> **Category:** Backend &nbsp;|&nbsp; **Confidence:** 92% &nbsp;|&nbsp;
> **Severity:** Critical &nbsp;|&nbsp; **Likely owner:** Backend / Platform team
> **Evidence:** Network status 500 · console error · assertion message
> **Recommended fix:** Inspect server logs for the failing endpoint; the defect
> is server-side, not in the test.

On every failure it automatically:

1. **Collects evidence** — exception, stacktrace, assertion, screenshot, DOM,
   console logs, network requests (method/url/status), API responses, and test
   metadata — into a `FailureContext`.
2. **Analyses the root cause** — classifies the failure (UI, Backend, API,
   Authentication, Authorization, Locator, Network, Performance, Infrastructure,
   Browser, Environment, Data, Configuration, Flaky Test, Unknown) with an
   **explained confidence score**.
3. **Finds similar past failures** (RAG) — "this failure resembles 3 previous
   ones" — from a pure-Python similarity index.
4. **Generates a fix recommendation** and a **bug report** — title, steps,
   expected/actual, severity, priority, owner, root cause, suggested fix — in
   Markdown, JSON, and HTML.
5. **Updates the run-history dashboard** — quality score, release readiness,
   trends, flaky detection, and run comparison.

### Higher-level analysis
- **Trend analytics** — most common failures, category distribution, flaky
  tests, and a day-by-day failure trend.
- **Release readiness** — a 0–100 score, a risk band, and a
  **Release / Investigate / Block** recommendation.
- **Failure clustering** — groups failures into Authentication / Security /
  Backend / UI / Timeout / Network / Infrastructure themes.

### Grounded and safe by design
- **No hallucinations** — every recommendation references actual collected
  evidence; unsupported claims are filtered out.
- **Secrets are masked** — passwords, JWTs, bearer tokens, API keys, and cookies
  are redacted *before* anything is stored or sent to an LLM.

---

## 4. The QA AI Assistant (talk to your test suite)

A command-line + conversational assistant lets you interrogate the run history in
plain English.

```powershell
python qa_ai.py analyze-last-failure
python qa_ai.py explain tests/test_ai_demo.py::test_ai_failure_analysis_end_to_end
python qa_ai.py find-flaky-tests
python qa_ai.py release-readiness
python qa_ai.py generate-bug
python qa_ai.py                # interactive chat mode
```

It understands questions such as "Why did the last run fail?", "Which tests are
flaky?", "Are we ready to release?", and "Generate a Jira bug." Each request is
routed to a modular **tool** that grounds its answer in the failure history
before responding.

---

## 5. Key capability: works with **zero setup and zero cost**

The AI layer runs **fully offline** by default with:
- a **deterministic heuristic analyzer** (rule-based, no LLM),
- a **pure-Python similarity index** (no external database),
- **local JSON** failure history.

No API keys. No extra installs. No internet. When you *want* more power, flip a
config switch to use a real LLM:

| Provider | How |
|----------|-----|
| OpenAI | `AI_PROVIDER=openai` + `OPENAI_API_KEY` |
| Azure OpenAI | `AI_PROVIDER=azure` + Azure vars |
| Anthropic Claude | `AI_PROVIDER=claude` + `ANTHROPIC_API_KEY` |
| Google Gemini | `AI_PROVIDER=gemini` + `GOOGLE_API_KEY` |
| **Local (Ollama)** | `AI_PROVIDER=ollama` — llama3 / mistral / deepseek, **no key, no cloud** |

Nothing else in the code changes — the provider is swapped by configuration only.

---

## 6. The demo, in one file

A single, framework-agnostic demo lives in
[`tests/test_ai_demo.py`](tests/test_ai_demo.py). It walks the whole product
story without a browser or an application under test:

```
a test fails → evidence is collected → the AI analyzes the failure →
root cause + fix are generated → reports are saved (md/json/html + bug report) →
the run-history dashboard updates
```

```powershell
pytest tests/test_ai_demo.py -v -o addopts=""
```

---

## 7. Project structure at a glance

```
multi-framework-tc-failure-ai-analyzer/
├── aiqa/               # the SDK: core domain, adapters, analysis engine, reporting
│   ├── core/           #   pure, framework-agnostic models + interfaces
│   ├── adapters/       #   Playwright, Selenium, Robot Framework, pytest, generic JSON
│   ├── analysis/       #   FailureAnalyzer (offline heuristics + optional LLM) + RAG
│   └── reporting/      #   reporters (md/json/html/console), bug builder, QualityPortal
├── qa_ai_engine/       # backward-compatible pytest + Playwright plugin + assistant
├── prompts/            # external, editable AI prompt templates
├── examples/           # runnable examples (generic, pytest, Playwright, Selenium, JSON)
├── tests/              # SDK unit tests + the single end-to-end demo test
├── docs/               # migration guide, demo storyboard, images
├── qa_ai.py            # QA AI Assistant CLI entry point
└── README.md           # product front door
```

---

## 8. Who is it for and why it matters

- **QA engineers** — stop triaging failures by hand; get a categorised root cause
  and a ready bug report instantly.
- **Developers** — know immediately whether a failure is *their* code, the test,
  the environment, or the backend.
- **Managers / release owners** — get a data-driven release-readiness score and
  trend insights instead of a wall of red/green.

It is designed to behave like an **AI-assisted Quality Engineering platform** you
might find inside a large tech company — modular, extensible, secure, documented,
and safe to run anywhere.

---

## 9. Quick start

```powershell
# 1. Setup
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Run the demo (offline, no keys)
pytest tests/test_ai_demo.py -v -o addopts=""

# 3. (Optional) Turn on the run-history dashboard, then open reports/index.html
$env:AIQA_PORTAL = "true"
pytest -o addopts=""
```

---

*For the full product overview see [README.md](README.md); for the SDK API see
[PACKAGE_README.md](PACKAGE_README.md).*
