# Roadmap

This roadmap is a living document — priorities may shift based on community
feedback. See [open issues](https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/issues)
for the current state, and [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) if you'd
like to help.

## Shipped

- ✅ Framework-agnostic core (`FailureContext` → `AnalysisResult`)
- ✅ Adapters: Playwright, Selenium, Robot Framework, pytest, generic JSON
- ✅ Offline heuristic analysis engine (no API keys required)
- ✅ Optional LLM providers (OpenAI + offline) with evidence grounding
- ✅ Reporters: Markdown, JSON, HTML, console, bug report
- ✅ Quality Portal: run-history dashboard, quality score, release readiness,
  flaky detection, run comparison, failure clustering
- ✅ CLI + chat assistant (`qa_ai.py`)

## In progress / next

- ⬜ First-class pytest plugin (`aiqa` entry point, zero-config)
- ⬜ More LLM providers as presets (Azure OpenAI, Anthropic, Gemini, Ollama)
- ⬜ Richer RAG over historical failures (better recall + dedup)
- ⬜ Cypress and Appium adapters shipped in-tree

## Exploring

- ⬜ VS Code extension (inline failure analysis)
- ⬜ MCP server exposing the assistant tools
- ⬜ Tracker integrations (Jira / GitHub Issues) from bug reports
- ⬜ Slack / Teams notifications for release-readiness signals

## Non-goals

- Running or orchestrating your tests — `aiqa` analyzes failures, it is not a
  test runner.
- Framework knowledge in the core — all framework specifics stay in adapters.
