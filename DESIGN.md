# Design Principles

This document explains *why* `aiqa` is built the way it is. The guiding idea:
**a failure analysis engine should know nothing about the tool that produced the
failure.** Everything else follows from that.

## The one-directional architecture

```
Adapters  ->  Core Domain  <-  AI Engine  ->  Reporting  ->  Output
```

Dependencies point inward toward a pure domain. Framework knowledge lives only
in adapters; the engine and reporters depend only on the domain model.

| Layer | Package | Knows a framework? | Depends on |
|-------|---------|--------------------|------------|
| Adapters | `aiqa.adapters` | **Yes** (only here) | core |
| Core domain | `aiqa.core` | No | standard library only |
| AI engine | `aiqa.analysis` | No | core (+ optional LLM SDK, lazy) |
| Reporting | `aiqa.reporting` | No | core |

## Clean Architecture

The **`FailureContext`** is the boundary object. Adapters translate the messy,
framework-specific outside world into this single, stable model; the engine and
reporters only ever see `FailureContext` and `AnalysisResult`. This keeps the
valuable logic (analysis, reporting, the quality portal) insulated from churn in
any test framework's API.

## SOLID

- **Single Responsibility** — each class does one thing: a `HeuristicClassifier`
  classifies, a `BugReportBuilder` builds bug reports, a `QualityScoreCalculator`
  scores. The Quality Portal is composed of many such single-purpose components.
- **Open/Closed** — add a framework by adding an adapter; add an output by adding
  a reporter; add an AI backend by adding an `LLMProvider`. The core never
  changes.
- **Liskov Substitution** — any `FrameworkAdapter`, `Reporter`, `LLMProvider`, or
  `SimilarityIndex` can be swapped for another without breaking callers.
- **Interface Segregation** — the extension points in `aiqa.core.interfaces` are
  small, focused protocols (`Analyzer`, `FrameworkAdapter`, `Reporter`,
  `LLMProvider`, `SimilarityIndex`).
- **Dependency Inversion** — high-level code depends on abstractions. The
  analyzer depends on the `LLMProvider` and `SimilarityIndex` *interfaces*, not on
  OpenAI or any concrete store.

## Dependency Injection

`FailureAnalyzer` accepts its collaborators as constructor arguments, each with a
safe default:

```python
FailureAnalyzer(
    llm=OfflineProvider(),      # or OpenAIProvider()
    index=NullIndex(),          # or InMemoryIndex()
    classifier=HeuristicClassifier(),
)
```

This makes the engine trivial to test (inject fakes) and trivial to upgrade
(inject a real LLM) without touching its logic.

## Offline First

The default path is **deterministic and dependency-free**: a heuristic
classifier plus pure-Python similarity search. No API keys, no network, no
flakiness. An LLM is strictly an *opt-in enhancement*, and even then every claim
stays grounded in the collected evidence, with secrets masked before anything
leaves the machine.

Why: analysis that only works with a paid API and a network connection is not
something teams can rely on in CI. Offline-first makes the SDK dependable by
default and better when you add an LLM.

## Patterns in use

- **Adapter Pattern** (`aiqa.adapters`) — convert each framework's failure data
  into the common `FailureContext`.
- **Strategy Pattern** (`LLMProvider`, `SimilarityIndex`, `Reporter`) —
  interchangeable algorithms selected at runtime.
- **Builder Pattern** (`FailureContextBuilder`, `BugReportBuilder`,
  `ExecutionReportBuilder`) — assemble complex objects step by step with a
  fluent, readable API.
- **Facade Pattern** (`QualityPortal`, top-level `analyze()` / `render()`) — a
  simple entry point over a set of cooperating components.
- **Composition over inheritance** — the portal and engine are *composed* from
  small single-responsibility parts rather than deep class hierarchies.

## What we deliberately avoid

- Framework imports in the core (enforced by review; see
  [CONTRIBUTING.md](CONTRIBUTING.md)).
- Hidden global state — configuration is explicit (`AiqaConfig`) and injectable.
- Being a test runner — `aiqa` analyzes failures; it does not run your tests.
