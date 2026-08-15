"""Bug report generation in Markdown, JSON, and HTML.

Turns a :class:`FailureRecord` + :class:`AnalysisResult` into a tracker-ready
bug report (Jira / Azure DevOps / GitHub style). Uses an LLM to draft prose
when configured, otherwise composes a solid deterministic report from the
evidence. Output is written under ``ai_reports/``.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from ._logging import get_logger
from .ai_config import AIConfig, ai_config
from .llm_client import BaseLLMClient, get_llm_client
from .models import AnalysisResult, BugReport, FailureRecord
from .prompt_builder import PromptBuilder
from .security import scrub

logger = get_logger("ai.bug_report_generator")

_PRIORITY_BY_SEVERITY = {
    "Blocker": "P1",
    "Critical": "P1",
    "Major": "P2",
    "Minor": "P3",
    "Trivial": "P4",
}


class BugReportGenerator:
    """Generates and renders bug reports."""

    def __init__(
        self,
        cfg: AIConfig = ai_config,
        llm: BaseLLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm or get_llm_client(cfg)
        self.prompts = prompt_builder or PromptBuilder(cfg)

    def generate(self, record: FailureRecord, analysis: AnalysisResult) -> BugReport:
        report = self._deterministic(record, analysis)
        if self.cfg.uses_llm and self.llm.is_available():
            try:
                self._augment_with_llm(report, record, analysis)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM bug drafting failed (%s); using deterministic report", exc)
        return report

    # ------------------------------------------------------------ generation
    def _deterministic(self, record: FailureRecord, analysis: AnalysisResult) -> BugReport:
        ev = record.evidence
        meta = record.metadata
        severity = analysis.severity.value
        environment = (
            f"{meta.environment or 'unknown'} | browser={meta.browser or 'n/a'} | "
            f"os={meta.os} | python={meta.python_version} | "
            f"framework={meta.framework_version} | commit={meta.git_commit or 'n/a'}"
        )
        steps = [
            "Run the automated suite against the target application environment.",
            f"Execute test '{record.test_name}'.",
            "Observe the failure at the assertion/step below.",
        ]
        return BugReport(
            title=f"[{analysis.category.value}] {record.test_name} — {analysis.root_cause[:80]}",
            description=analysis.root_cause or record.failure,
            environment=environment,
            steps=steps,
            expected="The test step completes successfully with valid data/UI state.",
            actual=(
                ev.assertion_message or record.failure or ev.exception_message or "Test failed."
            ),
            evidence=analysis.evidence,
            severity=severity,
            priority=_PRIORITY_BY_SEVERITY.get(severity, "P2"),
            owner=analysis.owner,
            root_cause=analysis.root_cause,
            suggested_fix=analysis.recommended_fix,
        )

    def _augment_with_llm(
        self, report: BugReport, record: FailureRecord, analysis: AnalysisResult
    ) -> None:
        prompt = self.prompts.build(
            "bug_report",
            {
                "test_name": record.test_name,
                "category": analysis.category.value,
                "root_cause": analysis.root_cause,
                "severity": analysis.severity.value,
                "environment": report.environment,
                "evidence": scrub(analysis.evidence, enabled=self.cfg.mask_secrets),
                "recommended_fix": analysis.recommended_fix,
            },
        )
        data = self.llm.complete_json(prompt)
        report.title = data.get("title") or report.title
        report.description = data.get("description") or report.description
        report.steps = data.get("steps") or report.steps
        report.expected = data.get("expected") or report.expected
        report.actual = data.get("actual") or report.actual
        report.priority = data.get("priority") or report.priority
        report.owner = data.get("owner") or report.owner
        report.suggested_fix = data.get("suggested_fix") or report.suggested_fix

    # -------------------------------------------------------------- rendering
    def to_markdown(self, report: BugReport) -> str:
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(report.steps, 1))
        evidence = "\n".join(f"- {e}" for e in report.evidence) or "- (none captured)"
        return (
            f"# {report.title}\n\n"
            f"**Severity:** {report.severity} &nbsp; **Priority:** {report.priority} &nbsp; "
            f"**Suggested Owner:** {report.owner}\n\n"
            f"## Description\n{report.description}\n\n"
            f"## Environment\n{report.environment}\n\n"
            f"## Steps to Reproduce\n{steps}\n\n"
            f"## Expected Result\n{report.expected}\n\n"
            f"## Actual Result\n{report.actual}\n\n"
            f"## Evidence\n{evidence}\n\n"
            f"## Suggested Root Cause\n{report.root_cause}\n\n"
            f"## Suggested Fix\n{report.suggested_fix}\n"
        )

    def to_html(self, report: BugReport) -> str:
        esc = html.escape
        steps = "".join(f"<li>{esc(s)}</li>" for s in report.steps)
        evidence = "".join(f"<li>{esc(e)}</li>" for e in report.evidence)
        return (
            "<section class='ai-bug-report'>"
            f"<h2>{esc(report.title)}</h2>"
            f"<p><strong>Severity:</strong> {esc(report.severity)} | "
            f"<strong>Priority:</strong> {esc(report.priority)} | "
            f"<strong>Owner:</strong> {esc(report.owner)}</p>"
            f"<h3>Description</h3><p>{esc(report.description)}</p>"
            f"<h3>Environment</h3><p>{esc(report.environment)}</p>"
            f"<h3>Steps to Reproduce</h3><ol>{steps}</ol>"
            f"<h3>Expected</h3><p>{esc(report.expected)}</p>"
            f"<h3>Actual</h3><p>{esc(report.actual)}</p>"
            f"<h3>Evidence</h3><ul>{evidence}</ul>"
            f"<h3>Suggested Root Cause</h3><p>{esc(report.root_cause)}</p>"
            f"<h3>Suggested Fix</h3><p>{esc(report.suggested_fix)}</p>"
            "</section>"
        )

    def save(self, report: BugReport, stem: str) -> dict[str, Path]:
        """Write markdown/json variants and return their paths.

        No standalone HTML is produced per test: the bug report is rendered inside
        the single consolidated per-run dashboard (with copy / download actions).
        """
        self.cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        variants: dict[str, str] = {
            "md": self.to_markdown(report),
            "json": json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        }
        for ext, content in variants.items():
            path = self.cfg.reports_dir / f"{stem}_bug.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write bug report %s: %s", path, exc)
        return paths
