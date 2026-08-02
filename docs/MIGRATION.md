# Migration Guide

## `playwright-tc-failure-ai-analyzer` → `multi-framework-tc-failure-ai-analyzer`

```
Old package                              New package
playwright-tc-failure-ai-analyzer   →    multi-framework-tc-failure-ai-analyzer
        (≤ 2.0.1)                                   (≥ 3.0.0)
```

The **import name is unchanged** — you still `import aiqa`. Only the
**distribution (PyPI) name** and the **GitHub repository name** changed.

---

## Why the rename?

The project **originally started as a Playwright-specific AI failure analyzer**.
It has since evolved into a **framework-agnostic Quality Engineering SDK** with an
adapter-based architecture that supports **Playwright, Selenium, Robot Framework,
and pytest** (plus Cypress, Appium, Requests, REST Assured, JUnit, NUnit, TestNG,
or anything that can emit JSON).

The old name implied a Playwright-only tool and no longer reflected what the
project does. **`multi-framework-tc-failure-ai-analyzer`** accurately describes
the multi-framework support.

---

## What changed

| | Old | New |
|---|-----|-----|
| PyPI package | `playwright-tc-failure-ai-analyzer` | `multi-framework-tc-failure-ai-analyzer` |
| GitHub repo | `amandeepsdet/playwright-tc-failure-ai-analyzer` | `amandeepsdet/multi-framework-tc-failure-ai-analyzer` |
| Version | `2.0.1` | `3.0.0` |
| Import name | `aiqa` | `aiqa` (unchanged) |
| Public API | `FailureAnalyzer`, `FailureContext`, … | unchanged |
| pytest plugin | `qa_ai_engine` | `qa_ai_engine` (unchanged) |

**No code changes are required** — only the package you install.

---

## Installation

```bash
pip install multi-framework-tc-failure-ai-analyzer
```

With optional extras:

```bash
pip install "multi-framework-tc-failure-ai-analyzer[openai]"   # LLM analysis
pip install "multi-framework-tc-failure-ai-analyzer[all]"      # everything
```

---

## Upgrade steps

1. **Uninstall the old package** (avoids a shadowed `aiqa` import):

   ```bash
   pip uninstall -y playwright-tc-failure-ai-analyzer
   ```

2. **Install the new package:**

   ```bash
   pip install multi-framework-tc-failure-ai-analyzer
   ```

3. **Your imports stay the same** — no source changes needed:

   ```python
   from aiqa import FailureAnalyzer, FailureContext, render
   ```

4. **Update any pinned dependencies** in `requirements.txt`,
   `pyproject.toml`, `setup.cfg`, `Pipfile`, or `poetry` from:

   ```
   playwright-tc-failure-ai-analyzer==2.0.1
   ```

   to:

   ```
   multi-framework-tc-failure-ai-analyzer>=3.0.0
   ```

5. **Update CI cache keys / lockfiles** if they reference the old name.

---

## Deprecation notice

The old `playwright-tc-failure-ai-analyzer` package (≤ 2.0.1) remains installable
for backward compatibility but is **deprecated**. **All future releases are
published only under `multi-framework-tc-failure-ai-analyzer`.** Please migrate at
your earliest convenience.

---

## Questions

Open an issue at
<https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer/issues>.
