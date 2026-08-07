# Examples

Minimal, runnable examples for the **aiqa** SDK. Every example is framework-agnostic
at its core — the only framework-specific code lives in the adapter it uses.

> From a source checkout the scripts add the repo root to `sys.path` automatically,
> so you can run them directly. In your own project, just
> `pip install multi-framework-tc-failure-ai-analyzer` and drop the bootstrap lines.

## Start here

| Example | File | Shows |
|---------|------|-------|
| **Canonical end-to-end demo** | [sdk_demo.py](sdk_demo.py) | The whole pipeline: `FailureContext → Analyzer → Root Cause → Fix → Bug → HTML → Run History` |

```bash
python examples/sdk_demo.py          # writes artifacts to sample_output/
```

## By framework / input

| Framework / input | File | Adapter |
|-------------------|------|---------|
| Plain Python (no framework) | [plain_python_example.py](plain_python_example.py) | `PytestAdapter` (plain-exception form) |
| Build a context by hand | [failure_context_example.py](failure_context_example.py) | `FailureContextBuilder` |
| JSON (Cypress, REST Assured, JUnit, CI, …) | [generic_json_example.py](generic_json_example.py) | `GenericAdapter` |
| pytest | [pytest_example.py](pytest_example.py) · [pytest/main.py](pytest/main.py) | `PytestAdapter` |
| Playwright | [playwright_example.py](playwright_example.py) · [playwright/main.py](playwright/main.py) | `PlaywrightAdapter` |
| Selenium | [selenium_example.py](selenium_example.py) | `SeleniumAdapter` |
| Robot Framework | [robotframework_example.py](robotframework_example.py) | `RobotFrameworkAdapter` |

## Tooling

| Example | File | Shows |
|---------|------|-------|
| CLI / assistant | [cli_example.py](cli_example.py) | Driving the QA AI assistant programmatically (same engine as `qa_ai.py`) |
| Quality portal | [generate_portal.py](generate_portal.py) | Building the run-history dashboard from several simulated runs |

## Run them all

```bash
python examples/plain_python_example.py
python examples/failure_context_example.py
python examples/generic_json_example.py
python examples/selenium_example.py
python examples/robotframework_example.py
python examples/cli_example.py
```
