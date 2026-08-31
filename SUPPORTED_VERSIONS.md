# Supported Versions

The SDK follows [Semantic Versioning](https://semver.org/). Security fixes are
applied to the **latest minor release of the current major line**; older minors
receive fixes only for **critical** vulnerabilities, at the maintainers'
discretion.

| Version | Status | Support |
|---------|--------|---------|
| 3.3.x   | Current stable | :white_check_mark: Full (features, fixes, security) |
| 3.2.x   | Previous minor | :warning: Critical security fixes only |
| 3.0.x – 3.1.x | Superseded | :x: Upgrade recommended |
| < 3.0   | End of life | :x: Unsupported |

> The latest release is always the recommended one. Pin a version in production
> (e.g. `multi-framework-tc-failure-ai-analyzer==3.3.*`) and upgrade minors
> deliberately after reading the [CHANGELOG](CHANGELOG.md).

## Supported Python versions

`aiqa` requires **Python 3.11+** and is tested on:

| Python | Supported          |
|--------|--------------------|
| 3.13   | :white_check_mark: |
| 3.12   | :white_check_mark: |
| 3.11   | :white_check_mark: |
| ≤ 3.10 | :x:                |

## Supported platforms

Windows, macOS, and Linux. The core SDK is pure Python and dependency-free;
optional features (e.g. an LLM provider) pull in extras only when enabled.

## What Semantic Versioning means here

The **public API** is what `import aiqa` exposes (see [API_REFERENCE.md](API_REFERENCE.md)).
Version bumps are decided against that contract:

- **MAJOR** (`x.0.0`) — a backward-incompatible change to the public API,
  supported adapters, or the `FailureContext` / `AnalysisResult` models; or a
  drop of a previously supported Python version. Announced ahead of time with a
  migration note.
- **MINOR** (`3.x.0`) — new, backward-compatible capability (e.g. a new adapter,
  reporter, CLI command, or the GitHub Action). Existing code keeps working.
- **PATCH** (`3.3.x`) — backward-compatible bug and security fixes only.

Additive changes (new optional fields, new modules, new extras) are **not**
breaking. Removing or renaming a public symbol, changing a documented default, or
altering serialized output shape **is** breaking and triggers a major bump.

## Python version policy

`aiqa` targets **actively supported CPython** releases and requires
**Python 3.11+**. Each release is tested in CI on the full matrix (3.11, 3.12,
3.13) via both GitHub Actions and CircleCI. When a CPython version reaches
end of life, support for it may be dropped in the next **minor** release; when a
new CPython version is released, it is added to the matrix once its dependencies
are compatible.

## Package & import names

| | Name | Status |
|---|------|--------|
| Install (PyPI) | `multi-framework-tc-failure-ai-analyzer` | Current — all releases ship here |
| Import | `aiqa` | Stable — unchanged across 2.x/3.x |
| Legacy PyPI | `playwright-tc-failure-ai-analyzer` (≤ 2.0.1) | Deprecated — no new releases |

The package ships **PEP 561** typing metadata (`py.typed`), so `mypy` / `pyright`
consume its type hints directly.

## Component support & deprecation

- **`aiqa`** — the modern, framework-agnostic SDK. Actively developed; all new
  features land here.
- **`qa_ai_engine`** — the legacy pytest/Playwright plugin and CLI/chat assistant.
  **Compatibility-only / maintenance**: kept so existing integrations keep
  working, no new feature development, and **not** currently scheduled for
  removal. Any future deprecation will be announced in the
  [CHANGELOG](CHANGELOG.md) with a migration path and a deprecation period of at
  least one minor release.

## Optional dependencies

The core install is intentionally light (standard library + `pytest`). Everything
else is opt-in via extras and is only imported when actually used:

| Extra | Enables |
|-------|---------|
| `playwright` | Evidence capture from live Playwright pages |
| `reports` | Allure / pytest-html integration |
| `openai`, `llm` | Cloud LLM providers (analysis upgrade) |
| `vector` | ChromaDB vector backend |
| `all` | Everything above |
| `dev` | Contributor toolchain (test, lint, format, type-check, coverage, build) |

Absence of any extra never breaks the offline path — the engine always has a
pure-Python fallback.

## Reporting a vulnerability

Please report security issues privately as described in
[SECURITY.md](SECURITY.md) — do **not** open a public issue for a suspected
vulnerability. Fixes are released as a patch on the current minor and noted in the
CHANGELOG.

## Upgrading

- Read the [CHANGELOG](CHANGELOG.md) for the target version first.
- Minor/patch upgrades within a major line are drop-in.
- For major upgrades, follow the migration notes (e.g.
  [docs/MIGRATION.md](docs/MIGRATION.md)).
- Verify with your own suite; the SDK is offline and side-effect-free by default.
