# API Reference

The public API is what `import aiqa` exposes. Everything here is imported from
the top-level package unless noted otherwise.

```python
from aiqa import (
    FailureAnalyzer, analyze,          # engine
    FailureContext, FailureContextBuilder,
    AnalysisResult, BugReport,
    render, get_reporter, available_formats,
    BugReportBuilder, QualityPortal,
    AiqaConfig, config,
)
from aiqa.adapters import (
    GenericAdapter, PytestAdapter, SeleniumAdapter,
    RobotFrameworkAdapter, PlaywrightAdapter,
)
```

- **Install name:** `multi-framework-tc-failure-ai-analyzer`
- **Import name:** `aiqa`

---

## Core domain

### `FailureContext`

The framework-agnostic description of one failure — the single input to the
engine. Build it with an adapter, the builder, or `from_dict`.

```python
FailureContext.from_dict({
    "metadata": {"test_name": "checkout::test_pay", "framework": "pytest"},
    "exception": {"type": "AssertionError", "message": "HTTP 500"},
    "evidence": {"network": [{"method": "POST", "url": "/api/pay", "status": 500}]},
    "execution": {"environment": "staging", "browser": "chromium"},
})
```

Key attributes: `metadata` (`FailureMetadata`), `exception` (`ExceptionInfo`),
`evidence` (`Evidence`), `execution` (`ExecutionContext`), `assertion_message`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_dict` | `(data: dict) -> FailureContext` | Build from a plain dict / parsed JSON. |
| `to_dict` | `() -> dict` | Serialise back to a dict. |

### `FailureContextBuilder`

Fluent builder used internally by every adapter. Each method returns `self`.

```python
context = (
    FailureContextBuilder()
    .with_test("payments::test_refund", suite="payments", framework="custom",
               tags=["regression"], execution_time_s=1.8)
    .with_exception_text(type="AssertionError", message="HTTP 403")
    .with_assertion("expected 200 but got 403")
    .with_network([{"method": "POST", "url": "/api/refund", "status": 403}])
    .with_logs(["Refund denied: missing scope"])
    .with_execution(environment="staging", url="/checkout/refund")
    .build()
)
```

Selected methods: `with_test(...)`, `with_exception(exc)`,
`with_exception_text(type, message, stacktrace)`, `with_assertion(message)`,
`with_screenshot(path)`, `with_dom(snapshot)`, `with_console(messages)`,
`with_network(events)`, `with_api_responses(responses)`, `with_logs(logs)`,
`with_artifact(name, path)`, `with_custom_evidence(key, value)`,
`with_execution(...)`, `build() -> FailureContext`.

### `AnalysisResult`

Structured output of the engine — the only input reporters consume.

| Attribute | Type | Notes |
|-----------|------|-------|
| `root_cause` | `RootCause` | `.summary`, `.category`, `.detail` |
| `confidence` | `ConfidenceScore` | `.value` (0–100), `.rationale` |
| `severity` | `Severity` | enum |
| `owner` | `str` | suggested owning team |
| `evidence` | `list[str]` | grounding for each claim |
| `recommendations` | `list[Recommendation]` | `.action`, `.rationale` (always ≥ 1) |
| `similar_failures` | `list[SimilarFailure]` | from similarity search |
| `category` | `FailureCategory` | convenience → `root_cause.category` |

Methods: `to_dict()`, `to_json(indent=2)`, `AnalysisResult.from_dict(data)`.

---

## Engine

### `FailureAnalyzer`

```python
FailureAnalyzer(
    *,
    llm: LLMProvider | None = None,          # default OfflineProvider()
    index: SimilarityIndex | None = None,    # default NullIndex()
    classifier: HeuristicClassifier | None = None,
    owner_overrides: dict[FailureCategory, str] | None = None,
    rag_top_k: int = 3,
    record_history: bool = True,
)

analyze(context: FailureContext) -> AnalysisResult
```

```python
result = FailureAnalyzer().analyze(context)          # offline
result = FailureAnalyzer(llm=OpenAIProvider()).analyze(context)  # LLM-enhanced
```

### `analyze` (convenience)

```python
analyze(context: FailureContext, **kwargs) -> AnalysisResult
```

Equivalent to `FailureAnalyzer(**kwargs).analyze(context)`.

---

## Reporting

### `render` / `get_reporter` / `available_formats`

```python
render(result: AnalysisResult, format: str = "markdown",
       context: FailureContext | None = None) -> str
```

`format` is one of `available_formats()` → `"markdown" | "json" | "html" |
"console"`. `get_reporter(format)` returns the `Reporter` instance if you want to
hold onto it.

```python
print(render(result, "html", context))
```

### `BugReportBuilder`  *(the bug generator)*

```python
build(result: AnalysisResult, context: FailureContext | None = None) -> BugReport
BugReportBuilder.to_markdown(bug: BugReport) -> str   # static
```

```python
bug = BugReportBuilder().build(result, context)
print(bug.title)                       # e.g. "[Backend] checkout::test_pay: ..."
open("bug.md", "w").write(BugReportBuilder.to_markdown(bug))
```

`BugReport` fields: `title`, `description`, `environment`, `steps`, `expected`,
`actual`, `evidence`, `severity`, `priority`, `owner`, `root_cause`,
`suggested_fix`.

---

## Quality Portal (run history)

### `QualityPortal`

The facade that aggregates executions into a self-contained HTML dashboard.

```python
QualityPortal(reports_dir: Path | str | None = None)   # default "reports" or $AIQA_REPORTS_DIR

begin_run(*, run_name="", framework="", environment="", browser="",
          os_name="", python_version="", package_version="", commit="") -> str
add_failure(result: AnalysisResult, context: FailureContext | None = None) -> None
add_success(test_id: str = "") -> None
add_skipped(test_id: str = "") -> None
finish_run() -> ExecutionRun | None      # writes run folder + refreshes index.html
regenerate_dashboard() -> None
```

```python
portal = QualityPortal("reports")
portal.begin_run(framework="pytest", environment="staging")
portal.add_failure(result, context)
portal.add_success("checkout::test_cart")
portal.finish_run()   # -> reports/index.html + reports/run_*/
```

### Portal internals (advanced)

These power the dashboard and can be used directly from
`aiqa.reporting.portal`:

| Class | Responsibility |
|-------|----------------|
| `ExecutionHistoryManager` | Persist and load `ExecutionRun` history (`history.json`). |
| `KnowledgeBase` | Remember failure signatures across runs; `recall(failure)`. |
| `QualityScoreCalculator` | Weighted 0–100 score + build-health band. |
| `ReleaseReadinessEngine` | READY / AT_RISK / NOT_READY verdict. |
| `RunComparisonEngine` | New / resolved / persisting failures between runs. |
| `FlakyDetector` | Pass/fail transition analysis over a window. |
| `DashboardGenerator` | Renders `index.html`. |

---

## Extension points (interfaces)

From `aiqa` (defined in `aiqa.core.interfaces`). Implement these to extend the
SDK without touching the core — see [DESIGN.md](DESIGN.md).

| Protocol | Method to implement | Purpose |
|----------|---------------------|---------|
| `FrameworkAdapter` | `collect_failure_context(...) -> FailureContext` | Support a new framework. |
| `Analyzer` | `analyze(context) -> AnalysisResult` | Swap the analysis strategy. |
| `Reporter` | `render(result, context) -> str` | Add an output format. |
| `LLMProvider` | `complete(prompt) -> str` / `is_available()` | Plug in an AI backend. |
| `SimilarityIndex` | `add(...)` / `search(...)` | Back the RAG similarity search. |

Built-in implementations: `OfflineProvider`, `OpenAIProvider` (providers);
`InMemoryIndex`, `NullIndex` (indexes); the five adapters listed at the top.

---

## Adapters

All adapters live in `aiqa.adapters` and expose
`collect_failure_context(...) -> FailureContext`.

| Adapter | Typical call |
|---------|--------------|
| `GenericAdapter` | `.collect_failure_context(payload_dict_or_json_or_path)` |
| `PytestAdapter` | `.collect_failure_context(exception=exc, test_name=...)` or `(item=, call=, report=)` |
| `SeleniumAdapter` | `SeleniumAdapter(driver=driver).collect_failure_context(exc, test_name=...)` |
| `RobotFrameworkAdapter` | `.collect_failure_context(test_name=, message=, status="FAIL", ...)` |
| `PlaywrightAdapter` | `PlaywrightAdapter(page=page, recorder=recorder).collect_failure_context(exc, test_name=...)` |

> `PlaywrightAdapter` / `PlaywrightEventRecorder` are lazy-exported so importing
> `aiqa.adapters` never imports Playwright.

See runnable usage for each in [examples/](examples/) and
[examples/README.md](examples/README.md).

---

## Configuration

### `AiqaConfig` / `config`

`config` is the process-wide default `AiqaConfig`. Configuration is read from
environment variables (e.g. `AIQA_REPORTS_DIR`, `AI_MASK_SECRETS`,
`AI_MASK_URLS`, and provider keys). Prefer injecting a config rather than relying
on globals in library code.
