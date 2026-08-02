# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/) format.

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

[3.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v3.0.0
[2.0.1]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v2.0.1
[2.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v2.0.0
[1.0.0]: https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/releases/tag/v1.0.0
