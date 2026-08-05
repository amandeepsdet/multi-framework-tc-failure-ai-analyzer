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

The ThingsBoard suite described below is the **reference demo project** that
exercises the SDK end to end.

---

## ThingsBoard IoT Dashboard — AI-Assisted Test Automation Platform (SDK demo)

A production-grade **test automation framework** for the ThingsBoard **Fuel Level
Monitoring** dashboard, extended with an **enterprise AI Failure Analysis Engine**
and an **interactive QA AI Assistant**.

In one line: it doesn't just tell you a test *failed* — it tells you **why it
failed, what broke, who should fix it, how confident it is, and how to fix it**,
then writes the bug report for you.

---

## 1. What is this, in plain words?

Imagine you have an IoT dashboard that shows fuel tanks — their fuel level,
temperature, battery, and connection status. You need to prove, automatically,
that:

- the website loads and lets you log in,
- the dashboard shows the right data in valid ranges,
- the data refreshes in real time,
- the backend REST APIs behind it work and are secure.

This project does all of that automatically. And when something breaks, an AI
layer investigates the failure like a senior engineer would.

The project has **two halves**:

| Half | What it does |
|------|--------------|
| **Core framework** | Runs UI + API tests against ThingsBoard and reports PASS/FAIL with screenshots, logs, and rich reports. |
| **AI layer** | On any failure, performs automatic root-cause analysis, generates a bug report, learns from history, and answers your questions in plain English. |

---

## 2. What the core framework does

### Two layers of testing
- **UI automation (Playwright)** — drives a real browser (Chromium/Firefox/WebKit):
  login, dashboard loading, telemetry columns, value ranges, and live refresh.
- **API automation (requests)** — hits the ThingsBoard REST API: JWT login,
  device discovery, telemetry retrieval, and negative/security cases.

### 16 automated test cases (TC-01 … TC-16)
- **Login:** form present, valid login, invalid login, empty credentials.
- **Dashboard:** loads and not blank, telemetry columns present, values in range,
  real-time refresh.
- **API:** auth returns JWT, unauthorized rejected, wrong password rejected,
  tampered/expired token rejected, device list, telemetry structure/types,
  telemetry ranges, missing-device handling.

### Engineering qualities
- **Page Object Model** — UI selectors and actions isolated from tests.
- **Reusable API client** — centralised JWT auth, retries, error handling.
- **Config-driven** — every URL, credential, timeout, and range lives in one
  place (`utils/config.py`) and is overridable by environment variables.
- **Secrets management** — credentials come from `.env` / env vars, never
  committed.
- **Rich reporting** — Allure (primary) + self-contained pytest-html (fallback).
- **Automatic diagnostics** — screenshot-on-failure, video retention, timestamped
  logs.
- **CI/CD-ready** — headless mode, env-based secrets, machine-readable reports,
  predictable artifact folders.

---

## 3. What the AI layer adds (the differentiator)

Normally a test framework only says:

> ❌ FAIL — "Widget not found"

This framework instead answers:

> 🧠 **Root cause:** A backend service returned HTTP 500, so the widget had no
> data to render.
> **Category:** Backend &nbsp;|&nbsp; **Confidence:** 92% &nbsp;|&nbsp;
> **Severity:** Critical &nbsp;|&nbsp; **Likely owner:** Backend / Platform team
> **Evidence:** Network status 500 · empty DOM widget · assertion message
> **Recommended fix:** Inspect server logs for the failing endpoint; the defect
> is server-side, not in the test.

### On every failure it automatically:
1. **Collects evidence** — screenshot, stacktrace, exception, assertion, current
   URL + page title, full DOM, browser console logs, network requests
   (method/url/status), API responses, and test metadata (browser, OS, Python
   version, git commit, timestamp, execution time, framework version).
2. **Stores it** as structured JSON in `failure_history/` (a searchable database).
3. **Analyses the root cause** — classifies into one of 15 categories (UI,
   Backend, API, Authentication, Authorization, Locator, Network, Performance,
   Infrastructure, Browser, Environment, Data, Configuration, Flaky Test,
   Unknown) with an **explained confidence score**.
4. **Finds similar past failures** (RAG) — "this failure resembles 3 previous
   ones" — from a vector database.
5. **Generates a bug report** — title, steps, expected/actual, severity,
   priority, owner, root cause, suggested fix — in Markdown, JSON, and HTML.
6. **Embeds the analysis** into the pytest-html report and attaches it to Allure.

### It also does higher-level analysis:
- **Trend analysis** — most common failures, category distribution, flaky tests,
  most-failing APIs/widgets, average runtime, day-by-day failure trend.
- **Release readiness** — a 0–100 score, a risk band (Low/Medium/High/Critical),
  and a **Release / Investigate / Block** recommendation.
- **Locator analysis** — when a UI selector breaks, it compares the expected
  locator against the live DOM and suggests replacements with similarity scores.
- **Visual analysis** (optional) — with a vision-capable model, inspects the
  failure screenshot: Is a widget missing? A spinner stuck? The dashboard blank?
  Layout broken? Login page shown?

### Grounded and safe by design
- **No hallucinations** — every recommendation references actual collected
  evidence; unsupported claims are filtered out.
- **Secrets are masked** — passwords, JWTs, bearer tokens, API keys, and cookies
  are redacted *before* anything is stored or sent to an LLM.

---

## 4. The QA AI Assistant (talk to your test suite)

A command-line + conversational assistant that lets you interrogate the framework
in plain English.

```powershell
python qa_ai.py analyze-last-failure
python qa_ai.py explain tests/test_ai_demo.py::test_demo_wrong_locator
python qa_ai.py search "temperature widget failures"
python qa_ai.py find-flaky-tests
python qa_ai.py release-readiness
python qa_ai.py explain-widget FuelLevel
python qa_ai.py generate-bug
python qa_ai.py suggest-locator "Fuel Level"
python qa_ai.py generate-test "Battery widget"
python qa_ai.py                # interactive chat mode
```

It understands natural language such as:
- "Why did TC-07 fail?"
- "Which tests are flaky?"
- "Are we ready to release?"
- "Generate a Jira bug."
- "Which APIs fail most often?"
- "Suggest a Playwright locator for Fuel Level."

Each request is routed to a modular **tool** (e.g. `AnalyzeFailureTool`,
`SearchHistoryTool`, `ReleaseReadinessTool`, `TrendAnalysisTool`) that grounds its
answer in the failure history + framework knowledge before responding.

---

## 5. Key capability: works with **zero setup and zero cost**

This is important: the AI layer is **off by default** and, when turned on, runs
**fully offline** with:
- a **deterministic heuristic analyzer** (rule-based, no LLM),
- a **pure-Python vector store** (no external database),
- **local JSON** failure history.

No API keys. No extra installs. No internet. So the whole project **runs on a
fresh machine** by just following the README.

When you *want* more power, flip a config switch to use a real LLM:

| Provider | How |
|----------|-----|
| OpenAI | `AI_PROVIDER=openai` + `OPENAI_API_KEY` |
| Azure OpenAI | `AI_PROVIDER=azure` + Azure vars |
| Anthropic Claude | `AI_PROVIDER=claude` + `ANTHROPIC_API_KEY` |
| Google Gemini | `AI_PROVIDER=gemini` + `GOOGLE_API_KEY` |
| **Local (Ollama)** | `AI_PROVIDER=ollama` — llama3 / mistral / deepseek, **no key, no cloud** |

Nothing else in the code changes — the provider is swapped by configuration only.

---

## 6. How it all fits together

```
                        ┌──────────────────────────────┐
   You run:  pytest ───►│  Core tests (UI + API)       │
                        └──────────────┬───────────────┘
                                       │  a test fails
                                       ▼
                        ┌──────────────────────────────┐
                        │  conftest failure hook        │
                        │  → collect all evidence       │
                        └──────────────┬───────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │  AIEngine                     │
                        │  ├─ analyze root cause        │
                        │  ├─ retrieve similar (RAG)    │
                        │  ├─ generate bug report       │
                        │  └─ store history + vectors   │
                        └──────────────┬───────────────┘
                                       ▼
                 Allure + pytest-html reports  &  ai_reports/
                                       ▲
                                       │  ask questions anytime
                        ┌──────────────┴───────────────┐
   You run: qa_ai.py ──►│  QA AI Assistant (CLI/chat)  │
                        └──────────────────────────────┘
```

---

## 7. Project structure at a glance

```
AmanDeep_ABB_Assignment/
├── pages/              # Page Object Model (login, dashboard) — UI selectors/actions
├── tests/              # 16 UI + API test cases, fixtures, and offline AI unit tests
├── utils/              # config, logger, helpers, ThingsBoard API client
├── ai/                 # AI Failure Analysis Engine (analyzer, LLM clients,
│                       #   evidence, RAG, reports, bug generator, trends)
├── assistant/          # QA AI Assistant (CLI + chat + modular tools, MCP-ready)
├── prompts/            # external, editable AI prompt templates
├── docs/               # test cases, bug report, and this document
├── failure_history/    # structured failure JSON (runtime)
├── ai_reports/         # AI analysis + bug reports md/json/html (runtime)
├── vector_db/          # RAG similarity index (runtime)
├── qa_ai.py            # assistant entry point
├── requirements.txt    # core deps (AI extras optional/commented)
├── pytest.ini          # run config + markers (ui/api/realtime/negative/ai)
├── README.md           # full setup + usage guide
└── skill.md            # how the codebase is wired (for AI agents/contributors)
```

---

## 8. Technology stack

| Tool | Role |
|------|------|
| **Python + Pytest** | Test runner, fixtures, markers, parametrization |
| **Playwright** | Cross-browser UI automation with auto-waiting |
| **requests** | REST API automation |
| **Allure + pytest-html** | Rich, shareable test reports |
| **python-dotenv** | Secrets/config from `.env` |
| **(Optional) OpenAI / Azure / Claude / Gemini / Ollama** | LLM-powered analysis |
| **(Optional) ChromaDB** | Scalable vector search for RAG |

---

## 9. Who is it for and why it matters

- **QA engineers** — stop triaging failures by hand; get a categorised root cause
  and a ready bug report instantly.
- **Developers** — know immediately whether a failure is *their* code, the test,
  the environment, or the backend.
- **Managers / release owners** — get a data-driven release-readiness score and
  trend insights instead of a wall of red/green.

It is designed to look and behave like an **AI-assisted Quality Engineering
platform** you might find inside a large tech company — modular, extensible,
secure, documented, and safe to run anywhere.

---

## 10. Quick start

```powershell
# 1. Setup (see README §9 for details)
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
copy .env.example .env      # then add TB_PASSWORD

# 2. Run the tests
pytest                       # full suite (UI + API) with reports

# 3. (Optional) Turn on the AI layer — offline, no keys needed
$env:AI_ENABLED = "true"
pytest

# 4. Ask the assistant
python qa_ai.py release-readiness
python qa_ai.py              # interactive chat
```

---

*For full setup and execution details, see [README.md](../README.md). For how the
codebase is wired internally, see [skill.md](../skill.md).*
