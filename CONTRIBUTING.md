# Contributing

Thanks for your interest in **multi-framework-tc-failure-ai-analyzer** (import
name `aiqa`). Contributions of all kinds are welcome.

## Getting started

```bash
git clone https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer.git
cd multi-framework-tc-failure-ai-analyzer

python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Unix:    source .venv/bin/activate

# Install the package with the full developer toolchain (test, lint, format,
# type-check, coverage, build). This is all a contributor needs.
pip install -e ".[dev]"

# Optional: runtime deps for the shared demo conftest (Playwright/requests/…).
pip install -r requirements.txt

# Optional but recommended: install the git hooks.
pre-commit install
```

## Running tests

The SDK, AI, and GitHub Action tests run fully offline (no browser, no secrets):

```bash
pytest tests/aiqa tests/ai tests/action -m "sdk or ai or action" -o addopts=""
```

Measure coverage (informational — no enforced threshold yet):

```bash
pytest --cov=aiqa --cov=qa_ai_engine --cov-report=term-missing
```

## Developer checks

All tooling is configured centrally in `pyproject.toml`. Run before submitting:

```bash
ruff check .        # lint (blocking in CI)
black --check .     # format check (blocking in CI)
mypy aiqa           # type check
pytest              # tests
```

## Architecture rules (please preserve)

The value of this project is its clean, framework-agnostic core. When
contributing:

- **No framework imports** in `aiqa/core`, `aiqa/analysis`, or `aiqa/reporting`.
  Framework libraries (Playwright, Selenium, …) may only be imported **lazily,
  inside adapter methods** under `aiqa/adapters`.
- The **AI engine accepts only a `FailureContext`** and returns an
  `AnalysisResult`.
- **Reporters consume only an `AnalysisResult`**.
- Add new framework support as a new **adapter**, not by branching the core.
- Keep the core dependency-free (standard library only).

## Style

- Format with **black** and lint with **ruff** before submitting (both are
  blocking in CI). Configuration lives in `pyproject.toml`; run `pre-commit
  install` to apply them automatically on commit.
- The package ships **PEP 561** typing metadata (`py.typed`); keep public
  functions typed and `mypy aiqa` clean.
- Add or update tests for any behavior change.
- Use clear, descriptive commit messages.

## Pull requests

1. Fork the repo and create a feature branch.
2. Make your change with tests.
3. Ensure `pytest`, `ruff`, and `black` all pass.
4. Open a PR describing the change and the motivation.

## Reporting issues

Use [GitHub Issues](https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/issues)
and pick the appropriate template. For security concerns, please avoid filing a
public issue with exploit details — describe the impact and contact the
maintainer.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
