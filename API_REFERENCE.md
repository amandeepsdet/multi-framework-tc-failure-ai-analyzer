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
    # Phase 1 — enterprise AI capabilities
    FailureClassifier, Classification, OwnerResolver, RiskLevel,
    ConfidenceReasoning,
    LocatorHealingEngine, LocatorRanker, HealingResult, LocatorSuggestion,
    heal_locator,
    BugGenerationEngine, BugExporter,
)
from aiqa.adapters import (
    GenericAdapter, PytestAdapter, SeleniumAdapter,
    RobotFrameworkAdapter, PlaywrightAdapter,
)
```

- **Install name:** `multi-framework-tc-failure-ai-analyzer`
- **Import name:** `aiqa`
- **Version:** 3.3.0 — see [CHANGELOG.md](CHANGELOG.md) for release history.

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

### `Evidence`

The collected signals attached to a `FailureContext` (`context.evidence`). Every
field is optional; the analyzer only ever grounds claims in what is present.

| Field | Type | Notes |
|-------|------|-------|
| `screenshot` | `str | None` | Path to a captured screenshot. |
| `dom_snapshot` | `str` | HTML snapshot (truncated to `max_chars`, default 20000). |
| `console` | `list[ConsoleMessage]` | Browser console messages (`.level`, `.text`). |
| `network` | `list[NetworkEvent]` | Requests (`.method`, `.url`, `.status`, `.duration_ms`). |
| `api_responses` | `list[dict]` | Raw API response payloads. |
| `logs` | `list[LogEntry]` | Application/test logs (`.level`, `.message`). |
| `artifacts` | `dict[str, str]` | Named file paths (trace, video, HAR, …). |
| `custom` | `dict[str, Any]` | Anything else (e.g. `locator`, `selector`). |

Helper: `available_sources() -> list[str]` names the non-empty evidence buckets,
used by reports to show what grounded the analysis.

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

### Enums

All are string enums (`str, Enum`), so `member.value` is a stable, human-readable
string safe to serialize. Each exposes a tolerant `coerce(value)` classmethod
that maps arbitrary input to the closest member (falling back to a sensible
default) — useful when ingesting external JSON.

**`FailureCategory`** (24 members) — `.value` shown:
`UI`, `Frontend`, `Locator`, `Element Not Found`, `Element Not Visible`, `API`,
`Backend`, `Authentication`, `Authorization`, `Security`, `Network`, `Timeout`,
`Performance`, `Infrastructure`, `Database`, `Dependency`, `Browser`, `Mobile`,
`Environment`, `Data`, `Configuration`, `Assertion`, `Flaky`, `Unknown`.
`FailureCategory.coerce(text)` keyword-matches free text (default `Unknown`).

**`Severity`** (highest → lowest): `Blocker`, `Critical`, `Major`, `Minor`,
`Trivial`.

**`RiskLevel`**: `Critical`, `High`, `Medium`, `Low`. `RiskLevel.coerce(value)`
defaults to `Medium`.

```python
from aiqa import FailureCategory, RiskLevel, Severity

FailureCategory.coerce("got HTTP 500 from server")   # -> FailureCategory.BACKEND
RiskLevel.coerce("blocker")                           # -> RiskLevel.CRITICAL
Severity.CRITICAL.value                               # -> "Critical"
```

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

`format` is one of `available_formats()`, which returns the registered formats
sorted alphabetically → `["console", "html", "json", "markdown"]` (the `render`
default is `"markdown"`). `get_reporter(format)` returns the `Reporter` instance
if you want to hold onto it.

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

`finish_run()` returns an `ExecutionRun` aggregating the whole execution:

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | `str` | e.g. `run_20260901_140355`. |
| `total` / `passed` / `failed` / `skipped` | `int` | Raw counts. |
| `pass_rate` | `float` | Percentage 0–100. |
| `avg_confidence` | `float` | Mean analysis confidence. |
| `quality_score` | `int` | Weighted 0–100 score. |
| `quality_band` | `str` | Excellent / Good / Warning / Poor. |
| `build_health` | `str` | Healthy / Warning / Critical. |
| `release_readiness` | `str` | `READY` / `AT RISK` / `NOT READY`. |
| `regressions` / `flaky_count` | `int` | Vs. previous run / over the window. |
| `categories` / `owners` / `severities` | `dict[str, int]` | Distributions. |
| `failures` | `list[RunFailure]` | Flattened per-failure records (with `.signature`). |
| `executive_summary` | `str` | Prose summary of the run. |

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
| `LLMProvider` | `complete_json(prompt, system="") -> dict` / `available() -> bool` | Plug in an AI backend. |
| `SimilarityIndex` | `add(doc_id, text, metadata)` / `search(text, top_k) -> list[dict]` | Back the RAG similarity search. |

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

`config` is the process-wide default `AiqaConfig`, populated from the environment
at import time. Prefer constructing and injecting your own `AiqaConfig()` rather
than relying on the global in library code. All variables are optional — the SDK
runs fully offline with none of them set.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AIQA_PROVIDER` | `offline` | Analysis backend: `offline` (heuristic) or `openai`. |
| `AIQA_MODEL` | `gpt-4o-mini` | Model name for the chosen provider. |
| `AIQA_API_KEY` | — | Provider key (falls back to `OPENAI_API_KEY`). |
| `AIQA_BASE_URL` | — | Custom / OpenAI-compatible endpoint. |
| `AIQA_BASE_DIR` | `.aiqa` | Where the similarity history is written. |
| `AIQA_ENABLE_HISTORY` | `false` | Persist a local similarity index for RAG. |
| `AIQA_RAG_TOP_K` | `3` | Number of similar past failures to retrieve. |
| `AIQA_REPORTS_DIR` | `reports` | Default output dir for `QualityPortal` (read by the portal). |

> The `AI_MASK_SECRETS` / `AI_MASK_URLS` masking toggles belong to the legacy
> `qa_ai_engine` pytest plugin, not the `aiqa` SDK.

---

## Phase 1 — Enterprise AI capabilities

All additions are framework-agnostic, offline-capable, and fully backward
compatible: existing APIs, adapters, and reports are unchanged.

### Intelligent Failure Classification

Every `AnalysisResult` now also carries `risk_level` (Critical/High/Medium/Low),
a `subcategory` and `reason` on its `root_cause`, and a `reasoning_detail`
(see below). For a standalone, structured verdict use `FailureClassifier`:

```python
from aiqa import FailureClassifier

c = FailureClassifier().classify(context)
c.category      # FailureCategory
c.subcategory   # e.g. "HTTP 500 Server Error"
c.confidence    # int 0..100
c.risk_level    # "Critical" | "High" | "Medium" | "Low"
c.owner         # resolved team, e.g. "Backend / Platform team"
c.reason        # human-readable justification
c.to_dict()
```

`OwnerResolver` maps a category to an owning team and is user-overridable:

```python
from aiqa import OwnerResolver
from aiqa.core import FailureCategory

resolver = OwnerResolver({FailureCategory.BACKEND: "Payments Squad"})
resolver.register(FailureCategory.SECURITY, "AppSec").resolve(FailureCategory.SECURITY)
```

### AI Confidence Reasoning

Every analysis produces an explainable `ConfidenceReasoning` at
`result.reasoning_detail`, rendered in the console, Markdown, HTML and JSON
reports.

```python
r = result.reasoning_detail
r.badge                # "🟢 High" | "🟡 Medium" | "🔴 Low"
r.confidence           # int
r.reasoning_points     # list[str]  — signals that support the verdict
r.supporting_evidence  # list[str]  — evidence sources used
r.conflicting_evidence # list[str]  — expected-but-missing corroboration
r.assessment           # one-sentence summary
r.low_confidence_note  # populated only when confidence is low
```

Confidence bands (`r.level` / `r.badge`): **High** ≥ 85 (🟢), **Medium** 60–84
(🟡), **Low** < 60 (🔴). The `low_confidence_note` is populated when confidence
falls below 70. `to_dict()` includes both `level` and `badge`.

### AI Locator Healing

Recover a broken UI locator from a DOM snapshot. Suggestions are ranked by
stability (test-id > id > role > name > text > css > xpath) and emitted for every
supported framework. Pass `target_text=` and/or `target_attributes=` to guide the
match.

```python
from aiqa import heal_locator     # or LocatorHealingEngine for reuse/injection

result = heal_locator("button.place-order", dom_html, target_text="Place order")
result.failure_reason              # why the old locator broke
best = result.best                 # highest-ranked LocatorSuggestion or None
best.playwright                    # "page.get_by_test_id('place-order-btn')"
best.selenium, best.css, best.xpath, best.robotframework
best.quality                       # "Best" | "Good" | "Weak"
result.to_json()
```

Empty or malformed DOM never raises — it returns a graceful, un-healed result.

### Intelligent Bug Generator

Turn an analysis into a professional, tracker-ready bug and export it anywhere.

```python
from aiqa import BugGenerationEngine, BugExporter

bug = BugGenerationEngine().build(result, context)
exporter = BugExporter()
exporter.to_markdown(bug)      # also: to_html/to_plaintext/to_json
exporter.to_jira_json(bug)     # also: to_azure_json/to_github_issue/to_linear_json
exporter.export_all(bug, "out/")  # writes bug.md/html/json/txt + all trackers
```

### Command-line interface

Installed as the `aiqa` console script (also `python -m aiqa`):

```bash
aiqa classify        context.json
aiqa explain-failure context.json
aiqa heal-locator    --old "button.place-order" --dom page.html --text "Place order"
aiqa generate-bug    context.json --format jira      # or --out ./bug
```

`context.json` is a serialized `FailureContext` (`FailureContext.to_json()`).
Add `--json` to `classify`/`explain-failure`/`heal-locator` for machine output.

### GitHub Action

For CI, the `analyze-failures` GitHub Action orchestrates this same public API
(adapters → `FailureAnalyzer` → `QualityPortal` → reporters) and publishes the
result to the Job Summary, a PR comment, and an artifact. It is documented
separately in [docs/github-action.md](docs/github-action.md) — it exposes no new
Python API.
