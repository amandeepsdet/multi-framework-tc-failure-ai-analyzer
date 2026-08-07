# Good First Issues

New to the project? These are self-contained, well-scoped tasks that are a great
way to make your first contribution. None of them require deep knowledge of the
whole codebase.

Before starting, please read [CONTRIBUTING.md](CONTRIBUTING.md) and the
architecture rules (the core must stay framework-agnostic).

## Adapters

- **Add a Cypress adapter** — map a Cypress failure JSON into a `FailureContext`
  (mirror `aiqa/adapters/generic.py` and `selenium.py`). Add an example under
  `examples/`.
- **Add an Appium adapter** — extract `current_url`, `page_source`, and driver
  logs, similar to the Selenium adapter.

## Reporters

- **Add a JUnit-XML reporter** — render an `AnalysisResult` as a `<testcase>`
  with the root cause in `<system-out>`. Follow `aiqa/reporting/markdown.py`.
- **Add a GitHub-flavored summary reporter** for `$GITHUB_STEP_SUMMARY`.

## Analysis

- **Add heuristics** for new categories (e.g. rate-limiting `429`, CORS errors)
  in `aiqa/analysis/heuristics.py`, with tests in `tests/aiqa/`.
- **Improve owner mapping** in `aiqa/analysis/owners.py` and make it
  configurable from `AiqaConfig`.

## Developer experience

- **Add type stubs / `py.typed` checks** and wire `mypy` into CI.
- **Expand `examples/`** with a runnable REST-Assured or JUnit JSON sample.
- **Docs polish** — fix a typo, clarify a section, or add a diagram.

## How to claim one

1. Comment on the matching
   [issue](https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/issues)
   (or open one) so we can avoid duplicate work.
2. Fork, branch, implement, and add tests.
3. Run `pytest -o addopts=""`, `ruff`, and `black`, then open a PR.

Small PRs are easier to review and merge — thank you!
