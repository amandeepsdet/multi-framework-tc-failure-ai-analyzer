"""Run the existing AIQA analysis pipeline over discovered failures.

Orchestration only: this module wires discovered :class:`FailureContext`s into
``FailureAnalyzer`` and ``QualityPortal`` — the very same engine, reporters,
release-readiness and knowledge base the SDK already ships. It adds no analysis
of its own.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiqa import (
    BugGenerationEngine,
    FailureAnalyzer,
    FailureContext,
    QualityPortal,
    heal_locator,
)
from aiqa.core.enums import FailureCategory
from aiqa.reporting.portal.models import ExecutionRun, RunFailure


@dataclass
class AnalysisOutcome:
    run: ExecutionRun | None = None
    report_dir: Path | None = None
    index_html: Path | None = None
    memories: dict[str, Any] = field(default_factory=dict)
    healed_locators: dict[str, str] = field(default_factory=dict)
    top_bug_markdown: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.run is not None


def _make_analyzer(*, use_llm: bool, provider: str, api_key: str) -> FailureAnalyzer:
    """Build the analyzer; only wire an external LLM when explicitly requested."""
    if not use_llm:
        return FailureAnalyzer()
    if provider.lower() in ("openai", "azure", "openai-compatible"):
        try:
            from aiqa import OpenAIProvider

            return FailureAnalyzer(llm=OpenAIProvider(api_key=api_key or None))
        except Exception:  # pragma: no cover - defensive, falls back offline
            return FailureAnalyzer()
    return FailureAnalyzer()


def run_analysis(
    contexts: list[FailureContext],
    *,
    passed: int = 0,
    skipped: int = 0,
    framework: str = "",
    environment: str = "ci",
    reports_dir: str | Path = "reports",
    commit: str = "",
    use_llm: bool = False,
    llm_provider: str = "none",
    llm_api_key: str = "",
    output_html: str | Path | None = None,
) -> AnalysisOutcome:
    """Analyze contexts and record an execution into the QualityPortal."""
    outcome = AnalysisOutcome()
    analyzer = _make_analyzer(use_llm=use_llm, provider=llm_provider, api_key=llm_api_key)

    portal = QualityPortal(reports_dir)
    portal.begin_run(
        framework=framework or "generic",
        environment=environment,
        os_name=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        commit=commit,
    )

    memories: dict[str, Any] = {}
    healed: dict[str, str] = {}
    top_bug = ""

    for ctx in contexts:
        result = analyzer.analyze(ctx)

        # Historical memory BEFORE this run is folded into the knowledge base.
        run_failure = RunFailure.from_analysis(result, ctx)
        try:
            memories[run_failure.signature] = portal.knowledge.recall(run_failure)
        except Exception:  # pragma: no cover - knowledge base is best-effort
            pass

        # Locator healing suggestion when the failure is locator-related.
        if result.root_cause.category in (
            FailureCategory.LOCATOR,
            FailureCategory.ELEMENT_NOT_FOUND,
            FailureCategory.ELEMENT_NOT_VISIBLE,
        ):
            dom = ctx.evidence.dom_snapshot or ""
            locator = str(ctx.evidence.custom.get("locator", "")) if ctx.evidence.custom else ""
            if dom and locator:
                healing = heal_locator(locator, dom, target_text=None)
                if healing.best is not None:
                    healed[ctx.test_name] = healing.best.playwright

        # A tracker-ready bug for the first (highest-signal) failure.
        if not top_bug:
            try:
                bug = BugGenerationEngine().build(result, ctx)
                top_bug = f"### {bug.title}\n\n{bug.description}\n\n**Suggested fix:** {bug.suggested_fix}"
            except Exception:  # pragma: no cover - bug gen is best-effort
                pass

        portal.add_failure(result, ctx)

    for _ in range(max(0, passed)):
        portal.add_success()
    for _ in range(max(0, skipped)):
        portal.add_skipped()

    run = portal.finish_run()
    outcome.run = run
    outcome.memories = memories
    outcome.healed_locators = healed
    outcome.top_bug_markdown = top_bug
    outcome.report_dir = Path(reports_dir)
    outcome.index_html = Path(reports_dir) / "index.html"

    # Optionally mirror the per-run HTML report to a stable output location.
    if output_html and run is not None:
        try:
            run_dir = Path(reports_dir) / run.run_id
            candidates = [run_dir / "ai_report.html", run_dir / "index.html"]
            src = next((c for c in candidates if c.exists()), None)
            dest = Path(output_html)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src is not None:
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem edge
            outcome.warnings.append(f"Could not copy HTML report: {exc}")

    return outcome
