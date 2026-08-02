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

pip install -r requirements.txt
```

## Running tests

The SDK tests run fully offline (no browser, no secrets):

```bash
pytest tests/aiqa tests/ai -m "sdk or ai" -o addopts=""
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

- Format with **black** and lint with **ruff** before submitting.
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
