---
name: framework-skill-abb-assignment
description: >-
  Guide for working inside the ThingsBoard "Fuel Level Monitoring" test-automation
  framework. Read this before adding or modifying UI tests, API tests, page
  objects, fixtures, or configuration. Explains how every module connects so an
  agent can extend the suite correctly without re-discovering the architecture.
---

# ThingsBoard Fuel Level Monitoring — Automation Framework Skill

This skill describes **how this specific project is wired together** so a coding
agent can automate changes (add a test, add a page object, tweak config) while
matching the existing conventions. It is a map of the codebase, not a tutorial.

## What this project is

A production-style Python test-automation framework that validates a ThingsBoard
IoT dashboard ("Fuel Level Monitoring") through two independent surfaces:

- **UI** — Playwright (sync API) driving Chromium, structured with the Page
  Object Model.
- **API** — a `requests`-based REST client hitting the ThingsBoard Cloud API.

Reporting is via **Allure** (primary) and **pytest-html** (fallback). Secrets
live in `.env`. The target is `https://thingsboard.cloud`.

## Directory map

```
ABB_Assignment/
├── pages/                 # Page Object Model (UI only)
│   ├── base_page.py       # BasePage: goto, capture(screenshot), dismiss_welcome_banner
│   ├── login_page.py      # LoginPage: locators + login/error flows
│   └── dashboard_page.py  # DashboardPage: dashboards nav + Tanks-table reads
├── tests/
│   ├── conftest.py        # fixtures + report/screenshot cleanup + failure hook
│   └── test_login.py      # TC-01..03, TC-16 (UI login, incl. negative)
├── utils/
│   ├── config.py          # Config dataclass + module-level `config` singleton
│   ├── api_client.py      # ThingsBoardAPIClient + ThingsBoardAPIError
│   ├── helpers.py         # screenshot_path, extract_number, in_range, poll_until
│   └── logger.py          # get_logger(name) -> console + file handlers
├── docs/
│   ├── test_cases.md      # 16 test cases (TC-01..TC-16)  <-- source of truth
│   ├── bug_report.md      # OBS-01..05 usability observations
│   ├── test_cases.xlsx    # generated from test_cases.md
│   └── bug_report.xlsx    # generated from bug_report.md (Observations table)
├── tools/
│   └── export_test_cases_xlsx.py  # regenerates both .xlsx from the .md tables
├── screenshots/           # runtime screenshots (cleaned each run)
├── reports/               # allure-results/ + report.html (cleaned each run)
├── logs/                  # automation_<timestamp>.log
├── .env / .env.example    # TB_PASSWORD, TB_JWT_TOKEN (secrets, gitignored)
├── pytest.ini             # addopts: headed, allure, html, screenshots, markers
└── requirements.txt
```

## How the layers connect

```
tests/  ──uses──►  fixtures (conftest.py)  ──build──►  pages/  &  api_client
  │                        │                              │
  │                        └── inject `config` singleton ─┘
  │
  └── assertions use helpers (extract_number, in_range, poll_until)
             all layers log via utils.logger.get_logger(name)
```

Key rule: **everything flows from `utils/config.py`**. There is a single
module-level `config` object imported everywhere (`from utils.config import config`).
Do not read env vars or hardcode URLs/credentials anywhere else.

### `utils/config.py` — the single source of settings
- Immutable `Config` dataclass; module exposes a ready `config` instance.
- Loads `.env` via `python-dotenv`. Secrets come from env: `TB_PASSWORD`,
  `TB_JWT_TOKEN`. Non-secret defaults are baked in.
- Important members: `base_url`, `username`, `password`, `jwt_token`,
  `dashboard_name` ("Fuel Level Monitoring"), `default_timeout_ms`,
  `poll_retries`, `poll_interval_seconds`, ranges (`fuel_level_range`,
  `temperature_range`, `battery_range`), `valid_connection_states`.
- Endpoint helpers: `login_endpoint`, `devices_endpoint` (`/api/tenant/devices`),
  `telemetry_endpoint(device_id)`.
- **When adding a tunable value, add it here — never inline it in a test.**

### `utils/api_client.py` — REST surface
- `ThingsBoardAPIClient` wraps `requests`; raises `ThingsBoardAPIError` on
  non-2xx (message includes the status code, e.g. "401").
- Methods: `login()`, `login_with(user, pw)`, `use_token(token)`, `token`,
  `get_devices()`, `get_first_device_id()`, `get_telemetry(device_id, keys=None)`,
  `get_telemetry_with_retry(device_id)` (uses `poll_until`).
- **API tests should call these methods**, not build requests directly.

### `pages/` — Page Object Model (UI)
- `BasePage(page, config)` gives every page: `goto(path)`, `capture(name)`
  (full-page screenshot into `screenshots/`), `dismiss_welcome_banner()`
  (handles the intermittent "Got it!" overlay).
- `LoginPage`: locators use resilient attribute/role selectors
  (`input[formcontrolname='username']`, "Sign in" button label). Methods:
  `open()`, `login(username=None, password=None)`, `get_error_toast()`,
  `wait_for_login_success()`.
- `DashboardPage`: the dashboard's key widget is a **"Tanks" table**; telemetry
  is read from table **columns**, not separate widgets. `_COLUMNS` maps
  fuel/temperature/battery/connection to `mat-column-defN` CSS classes.
  Methods: `open_dashboards()`, `open_dashboard_by_name()`,
  `wait_for_tanks_table()`, `is_loaded()`, `has_column(name)`,
  `read_tank_metrics(row_index=0)`, `dashboard_text()`.
- **New UI interactions belong in a page object, never inline in a test.**

### `tests/conftest.py` — fixtures & lifecycle
- `pytest_configure`: deletes previous screenshots + `report.html` so every run
  is fresh (resilient to OneDrive file locks via try/except).
- Fixtures: `api_client` (session-scoped, authenticated), `login_page` (opened),
  `authenticated_page` (logs in + screenshots), `dashboard_page`.
- `pytest_runtest_makereport` hook captures a screenshot on any UI failure.
- **Optional AI portal:** when `AI_ENABLED`/`AIQA_PORTAL` is set, the same hooks
  feed each failure into `aiqa`'s `QualityPortal`, producing a multi-run
  dashboard at `reports/index.html` (per-run reports under `reports/run_*/`).
  Disabled by default, so normal runs are unaffected.

### `utils/helpers.py` — shared assertions/util
- `extract_number(text)` (first number from strings like "12 °C"),
  `in_range(value, bounds)`, `poll_until(action, predicate, retries,
  interval_seconds, description)` → `(success, last_result)`.
- **Range/refresh checks must use these**, keeping tests declarative.

## Test-case numbering contract

`docs/test_cases.md` is the **source of truth** for test IDs. Each test's
`@allure.title("TC-NN: ...")` and its docstring must match the doc. Current map:

| ID | File | Test |
|----|------|------|
| TC-01..03 | test_login.py | form elements / valid / invalid login |
| TC-16 | test_login.py | empty credentials blocked |

If you add/renumber a test, update **all three** in sync: the doc, the
`@allure.title`, and the docstring — then regenerate the xlsx (see below).

## Conventions an agent must follow

1. **Config-first**: import `config`; never hardcode URLs, credentials, timeouts,
   or ranges. Add new knobs to `utils/config.py`.
2. **POM for UI**: put selectors and page actions in `pages/`; tests only call
   page methods and assert.
3. **API via client**: use `ThingsBoardAPIClient`; expect `ThingsBoardAPIError`
   for negative cases (`with pytest.raises(ThingsBoardAPIError)`).
4. **Resilient selectors**: prefer `formcontrolname`, roles, header text, and the
   `mat-column-defN` classes already in use. Avoid brittle nth-child chains.
5. **No hardcoded sleeps** except deliberate polling via `poll_until` /
   `wait_for_timeout` in negative flows.
6. **Allure + logging on every test**: decorate with
   `@allure.feature/story/severity/title`, add `@pytest.mark.<ui|api|realtime|negative>`,
   and log START/END via `get_logger(name)`.
7. **Screenshots**: call `capture("name")` at meaningful points; failures are
   auto-captured by the conftest hook.
8. **Secrets stay in `.env`** (gitignored). Never commit real passwords/JWTs;
   update `.env.example` when adding a new secret key.

## Recipes (how to automate common changes)

**Add a new UI test**
1. Add/extend a method on the relevant page object in `pages/`.
2. Add the test to the matching `tests/test_*_ui.py` with allure decorators,
   marker, logging, and a `capture()`.
3. Add a `TC-NN` row to `docs/test_cases.md`; mirror the ID in the allure title.
4. Regenerate xlsx.

**Add a new API test**
1. Add a reusable method to `ThingsBoardAPIClient` if a new endpoint is needed.
2. Add the test to a `tests/test_*.py` module (assert types/ranges via
   `helpers`, or `pytest.raises(ThingsBoardAPIError)` for negatives).
3. Update the doc + allure title; regenerate xlsx.

**Add a config value**: add the field/default to `Config`, read it in the
page/client/test. Secrets → `.env` + `.env.example`.

**Regenerate the Excel docs** after editing `docs/*.md`:
```powershell
& ".venv/Scripts/python.exe" tools/export_test_cases_xlsx.py
```

## AI Failure Analysis Engine (`ai/`) — how it is wired

Optional layer that adds AI-assisted root-cause analysis on top of PASS/FAIL. It
is **OFF by default** (`AI_ENABLED=false`) and, when enabled, works **fully
offline** (heuristic analyzer + JSON vector store + hash embeddings) with no keys
or extra deps. Cloud LLMs / ChromaDB are opt-in via config only.

### AI directory map
```
ai/
├── ai_config.py           # AIConfig dataclass + `ai_config` singleton (env-driven)
├── security.py            # secret masking (mask_text / scrub) before any LLM call
├── models.py              # Evidence, FailureRecord, AnalysisResult, BugReport, enums
├── llm_client.py          # BaseLLMClient + OpenAI/Azure/Claude/Gemini/Ollama + factory
├── embeddings.py          # BaseEmbedder + HashEmbedder(default)/OpenAIEmbedder
├── vector_store.py        # BaseVectorStore + JSONVectorStore(default)/ChromaVectorStore
├── history_store.py       # HistoryStore: failure JSON under failure_history/
├── prompt_builder.py      # PromptBuilder: loads prompts/*.txt, {{TOKEN}} injection
├── evidence_collector.py  # PageEventRecorder + EvidenceCollector (metadata, git)
├── failure_analyzer.py    # FailureAnalyzer: heuristic rules + LLM + RAG grounding
├── locator_analyzer.py    # LocatorAnalyzer: DOM diff → suggested locators
├── visual_analyzer.py     # VisualAnalyzer: optional LLM-vision screenshot Q&A
├── trend_analyzer.py      # TrendAnalyzer + ReleaseReadiness scoring
├── report_generator.py    # ReportGenerator: analysis + trend md/json/html
├── bug_report_generator.py# BugReportGenerator: bug md/json/html
└── engine.py              # AIEngine façade (dependency-injected; used by conftest)

assistant/                 # QA AI Assistant (CLI + chat + tools, MCP-ready)
├── tool_registry.py       # BaseTool (execute/description/examples) + ToolRegistry
├── assistant.py           # QAAssistant service (all capabilities, front-end-agnostic)
├── chat_engine.py         # NL intent routing + interactive REPL
├── commands.py            # argparse CLI ↔ service dispatch
└── qa_ai.py               # in-package entry (root qa_ai.py mirrors it)

prompts/                   # external prompt templates (root_cause, bug_report, ...)
```

### How AI hooks into the run
- `tests/conftest.py` imports `ai.ai_config`. When `AI_ENABLED`:
  - an **autouse** `_ai_event_recorder` fixture attaches a `PageEventRecorder`
    to the `page` (UI tests only) to buffer console + network live;
  - the existing `pytest_runtest_makereport` failure hook calls
    `AIEngine.analyze_failure(...)`, then attaches results to Allure and
    pytest-html. **All AI work is wrapped in try/except — it can never fail a run.**

### Conventions for extending the AI engine
1. **Config-first (again):** add new AI knobs to `ai/ai_config.py` (env-driven),
   never read `os.getenv` elsewhere. Keep every default offline/no-secret.
2. **Program to interfaces:** add an LLM provider by subclassing `BaseLLMClient`
   and `register_provider("name", Cls)`; a vector back-end via `BaseVectorStore`;
   an embedder via `BaseEmbedder`. Do not couple call sites to a vendor SDK, and
   import SDKs **lazily** inside methods.
3. **Prompts are data:** never hardcode prompt strings in code — add/edit a
   `prompts/<name>.txt` using `{{TOKEN}}` placeholders and render via
   `PromptBuilder.build(name, context)`.
4. **Ground everything:** heuristic and LLM outputs must reference real evidence
   (`Evidence.available_sources()`); LLM evidence is filtered by `_ground_evidence`.
5. **Mask before send:** any evidence leaving the process must pass through
   `ai.security.scrub(...)`; never send passwords/JWTs.
6. **Keep it non-breaking:** guard AI usage behind `ai_config.enabled`; failures
   in AI code must be caught and logged, not raised.
7. **Test offline:** add unit tests under `tests/ai/` marked `@pytest.mark.ai`
   that exercise the heuristic/JSON paths with no network. Run them with
   `pytest tests/ai -m ai -o addopts=""`.

### QA Assistant recipes
- **Add a capability:** implement a method on `QAAssistant`, register it as a
  tool in `_register_tools`, and add a routing `Intent` in `chat_engine.py`;
  add a subcommand in `commands.py` if it needs a CLI verb.
- **Expose via MCP later:** wrap `QAAssistant` methods — they are pure,
  serialisable services with no terminal coupling.

```

## Running (Windows PowerShell)

Use the venv Python directly; `python`/`python3` are not on PATH — use `py` or the
venv path. Chain commands with `;` (no `&&`).

```powershell
# All tests (headed, fresh reports — defaults come from pytest.ini)
& ".venv/Scripts/python.exe" -m pytest

# One test, watch it, slow motion
& ".venv/Scripts/python.exe" -m pytest tests/test_login.py::test_valid_login_succeeds --headed --slowmo 300 -v

# By marker
& ".venv/Scripts/python.exe" -m pytest -m api
```

`pytest.ini` `addopts` already set: `--headed --browser chromium
--screenshot only-on-failure --video retain-on-failure
--alluredir=reports/allure-results --clean-alluredir
--html=reports/report.html --self-contained-html`. Markers: `ui`, `api`,
`realtime`, `negative`. Allure CLI + Java are required only to *render* the
Allure report; results are always written.

## Known project facts / gotchas

- Base URL is `https://thingsboard.cloud` (the original demo host was inactive).
- Device list endpoint is `/api/tenant/devices` (NOT `deviceInfos` on cloud).
- Login button label is "Sign in"; login can take 10–15s — waits are patient.
- The "Got it!" welcome banner intermittently intercepts clicks; always dismissed
  via `dismiss_welcome_banner()`.
- Telemetry may be momentarily empty; the realtime test (TC-07) does not fail on
  first observation — it polls and reports.
- OneDrive can lock screenshot files; cleanup is intentionally fault-tolerant.
