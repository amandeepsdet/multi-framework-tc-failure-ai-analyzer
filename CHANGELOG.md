# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

### Added
- **GitHub Action** (`.github/actions/analyze-failures`) — a reusable, composite
  action that analyzes failed test artifacts with the AIQA SDK and publishes the
  results to the GitHub **Job Summary**, a **Pull Request comment** (create/update
  by marker, never duplicated), and an uploaded **artifact**. Framework-agnostic
  (pytest, Playwright, Selenium, Robot Framework, and generic JUnit/JSON), offline
  by default, non-blocking by default, with an optional `fail-on-error` quality
  gate. Orchestration only — it reuses the existing adapters, `FailureAnalyzer`,
  `FailureClassifier`, `QualityPortal` (release readiness + knowledge base) and
  reporters; it adds no analysis engine of its own. Inputs, outputs, PR-comment
  behavior, permissions and security are documented in
  [docs/github-action.md](docs/github-action.md). Includes local test scripts and
  automated tests under `tests/action/`.

## [3.2.0] — 2026-08-09

Enterprise AI capabilities. Purely additive and fully backward compatible — the
architecture, public APIs, adapters, and existing reports are unchanged, and no
new runtime dependencies are introduced (everything is standard-library, offline).

### Added
- **Intelligent Failure Classification** — expanded `FailureCategory`, a new
  `RiskLevel`, `subcategory`/`reason` on `RootCause`, and `risk_level` on
  `AnalysisResult`. New `FailureClassifier` produces a structured `Classification`
  (category, subcategory, confidence, owner, risk, reason); new `OwnerResolver`
  makes team routing overridable.
- **AI Confidence Reasoning** — new `ConfidenceReasoning` attached to every
  `AnalysisResult` (`result.reasoning_detail`) explaining the verdict with a
  confidence badge, supporting signals, conflicting evidence, and a
  low-confidence note. Rendered in the console, Markdown, HTML and JSON reports.
- **AI Locator Healing** (`aiqa.healing`) — `LocatorHealingEngine` /
  `heal_locator` recover a broken locator from a DOM snapshot and emit ranked,
  multi-framework suggestions (Playwright, Selenium, CSS, XPath, Robot Framework).
- **Intelligent Bug Generator** — `BugGenerationEngine` builds a professional,
  enriched `BugReport`; `BugExporter` exports Markdown/HTML/JSON/plaintext, Jira,
  Azure Boards, GitHub Issues and Linear (plus `export_all`).
- **`aiqa` command-line interface** — `classify`, `explain-failure`,
  `heal-locator`, `generate-bug` subcommands (console script and `python -m aiqa`).
- New examples and expanded API reference / README documentation.

## [3.1.0] — 2026-08-03

Minor release. Adds a new **multi-run reporting layer** on top of the existing
single-result reporters. Fully backward compatible — the core domain models, the
adapters, and the AI analysis engine are unchanged, and no new runtime
dependencies are introduced (the portal is pure standard library).

### Added
- **Quality Intelligence Platform** (`aiqa.reporting.portal`) — a historical,
  multi-execution reporting portal exposed through a single facade,
  `QualityPortal`, also re-exported at the top level (`from aiqa import QualityPortal`):
  - **Execution history** — every run is persisted to its own `run_*/` folder
    with a self-contained HTML report, plus a regenerated landing `index.html`
    dashboard that discovers all runs (`history.json` / `latest.json`).
  - **Quality Score & build health** — a weighted 0–100 score with
    Excellent / Good / Warning / Poor bands and a Healthy / Warning / Critical
    build-health signal.
  - **Release readiness** — a READY / AT_RISK / NOT_READY verdict with reasons.
  - **Run-over-run comparison** — new / resolved / persisting failures and
    regression detection, keyed by a stable failure signature.
  - **Flaky-test detection** — heuristic pass/fail transition analysis over a
    sliding window.
  - **Knowledge base / failure memory** — recurring-failure recall, occurrence
    counts, and the most successful historical fix.
  - **Trend analysis** — pass rate, failure count, confidence, duration, and
    quality score across recent runs.
  - **AI executive summary & insights** — prose run summaries plus cross-run
    insights (category shifts, first-seen HTTP statuses, owner hotspots).
  - **Failure clustering** — groups failures into Authentication / Security /
    Backend / UI / Timeout / Network / Infrastructure themes.
- **Automatic portal generation** in the reference pytest suite — the demo
  `conftest.py` wires `QualityPortal` into the pytest lifecycle so a portal is
  produced on every run (gated by `AI_ENABLED` / `AIQA_PORTAL`).
- **`examples/generate_portal.py`** — a standalone script that generates a
  multi-run portal from synthetic scenarios.

### Unchanged (backward compatible)
- Import name `aiqa` and the entire existing public API.
- `FailureContext`, `AnalysisResult`, all adapters, and the analysis engine.
- The single-result reporters (`markdown`, `json`, `html`, `console`) and
  `BugReportBuilder`.

---

## [3.0.0] — 2026-08-01

Major release. **The package identity changed**, so this is a major version bump
even though the public Python API (`import aiqa`) is unchanged.

### Added
- **Multi-framework architecture** via an adapter layer:
  - Playwright
  - Selenium
  - Robot Framework
  - pytest
  - Generic JSON adapter (Cypress, Appium, Requests, REST Assured, JUnit, NUnit, TestNG, or any tool that emits JSON)
- **AI Root Cause Analysis** — evidence-grounded category, confidence, severity, and owner.
- **Bug Generator** — tracker-ready bug reports (Markdown / JSON / HTML).
- **Fix Recommendation Engine** — actionable recommendations per failure category.
- **CLI** — interactive QA assistant (`qa-ai`).
- **Offline AI** — deterministic heuristic engine + pure-Python similarity search, zero API keys required.
- **SDK Architecture** — clean public API: `from aiqa import FailureAnalyzer, FailureContext`.
- **Migration Guide** ([docs/MIGRATION.md](docs/MIGRATION.md)) and **CHANGELOG**.
- **CI/CD** — GitHub Actions workflows for tests and PyPI publishing; issue/PR templates and contributing guide.

### Changed
- **Package renamed**: `playwright-tc-failure-ai-analyzer` → `multi-framework-tc-failure-ai-analyzer`.
- **Repository renamed**: `amandeepsdet/playwright-tc-failure-ai-analyzer` → `amandeepsdet/multi-framework-tc-failure-ai-analyzer`.
- **Documentation** updated throughout (README, badges, install commands, project URLs).

### Deprecated
- The old PyPI package **`playwright-tc-failure-ai-analyzer`** (≤ 2.0.1). It
  remains installable for backward compatibility, but **all future releases ship
  only under `multi-framework-tc-failure-ai-analyzer`**.

### Unchanged (backward compatible)
- Import name `aiqa` and the entire public API.
- The `qa_ai_engine` pytest plugin (entry point `qa_ai_engine`).

---

## [2.0.1] — 2026-07-29
- Documentation rewrite positioning the project as a framework-agnostic SDK;
  packaging metadata refresh.

## [2.0.0] — 2026-07-29
- Introduced the framework-agnostic `aiqa` SDK (core domain, adapters, analysis,
  reporting) alongside the original `qa_ai_engine` pytest plugin.

## [1.0.0]
- Initial release as `playwright-tc-failure-ai-analyzer` — pytest + Playwright AI
  failure analysis engine.

[3.1.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v3.1.0
[3.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v3.0.0
[2.0.1]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v2.0.1
[2.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v2.0.0
[1.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v1.0.0
