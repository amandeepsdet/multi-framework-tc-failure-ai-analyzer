"""AI execution report rendering (Markdown / JSON / HTML).

Produces the per-failure analysis report written to ``ai_reports/`` and the
HTML fragment embedded into the pytest-html report / attached to Allure. Also
renders the aggregate trend + release-readiness report.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .models import AnalysisResult, FailureRecord
from .trend_analyzer import ReleaseReadiness, TrendReport

logger = get_logger("ai.report_generator")

_CONFIDENCE_COLORS = [(85, "#1a7f37"), (60, "#bf8700"), (0, "#cf222e")]


def _confidence_color(confidence: int) -> str:
    for threshold, color in _CONFIDENCE_COLORS:
        if confidence >= threshold:
            return color
    return "#cf222e"


class ReportGenerator:
    """Renders analysis and trend reports in multiple formats."""

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg

    # ---------------------------------------------------------- single failure
    def to_markdown(self, record: FailureRecord, analysis: AnalysisResult) -> str:
        evidence = "\n".join(f"- {e}" for e in analysis.evidence) or "- (none)"
        similar = (
            "\n".join(
                f"- {s.get('test_name', '?')} ({s.get('category', '?')}, "
                f"{s.get('similarity', 0)}% similar)"
                for s in analysis.similar_failures
            )
            or "- (none found)"
        )
        return (
            f"# AI Failure Analysis — {record.test_name}\n\n"
            f"- **Category:** {analysis.category.value}\n"
            f"- **Confidence:** {analysis.confidence}%\n"
            f"- **Severity:** {analysis.severity.value}\n"
            f"- **Likely Owner:** {analysis.owner}\n"
            f"- **Analysed by:** {analysis.source}\n"
            f"- **Timestamp:** {record.timestamp}\n\n"
            f"## Root Cause\n{analysis.root_cause}\n\n"
            f"## Evidence\n{evidence}\n\n"
            f"## Recommended Fix\n{analysis.recommended_fix}\n\n"
            f"## Reasoning\n{analysis.reasoning}\n\n"
            f"## Similar Past Failures\n{similar}\n"
        )

    def to_html(self, record: FailureRecord, analysis: AnalysisResult) -> str:
        """Compact self-contained HTML fragment for pytest-html / Allure."""
        esc = html.escape
        color = _confidence_color(analysis.confidence)
        evidence = "".join(f"<li>{esc(e)}</li>" for e in analysis.evidence)
        similar = "".join(
            f"<li>{esc(str(s.get('test_name', '?')))} — {esc(str(s.get('category', '?')))} "
            f"({s.get('similarity', 0)}%)</li>"
            for s in analysis.similar_failures
        )
        return (
            "<div class='ai-analysis' style='border:1px solid #d0d7de;border-radius:8px;"
            "padding:12px;margin:8px 0;font-family:sans-serif'>"
            "<h3 style='margin-top:0'>&#129504; AI Failure Analysis</h3>"
            f"<p><strong>Root Cause:</strong> {esc(analysis.root_cause)}</p>"
            f"<p><strong>Category:</strong> {esc(analysis.category.value)} &nbsp;|&nbsp; "
            f"<strong>Severity:</strong> {esc(analysis.severity.value)} &nbsp;|&nbsp; "
            f"<strong>Owner:</strong> {esc(analysis.owner)}</p>"
            f"<p><strong>Confidence:</strong> "
            f"<span style='color:{color};font-weight:bold'>{analysis.confidence}%</span> "
            f"<span style='color:#57606a'>(via {esc(analysis.source)})</span></p>"
            f"<p><strong>Evidence:</strong></p><ul>{evidence or '<li>(none)</li>'}</ul>"
            f"<p><strong>Suggested Fix:</strong> {esc(analysis.recommended_fix)}</p>"
            + (f"<p><strong>Similar Failures:</strong></p><ul>{similar}</ul>" if similar else "")
            + "</div>"
        )

    def save(self, record: FailureRecord, analysis: AnalysisResult, stem: str) -> dict[str, Path]:
        self.cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        variants = {
            "md": self.to_markdown(record, analysis),
            "json": json.dumps(
                {"record": record.to_dict(), "analysis": analysis.to_dict()},
                indent=2,
                ensure_ascii=False,
            ),
            "html": self.to_html(record, analysis),
        }
        paths: dict[str, Path] = {}
        for ext, content in variants.items():
            path = self.cfg.reports_dir / f"{stem}_analysis.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write analysis report %s: %s", path, exc)
        return paths

    # ---------------------------------------------------------- trend / release
    def trend_markdown(self, trend: TrendReport, readiness: ReleaseReadiness) -> str:
        def _rows(items: list[dict[str, Any]], key: str, count_key: str = "count") -> str:
            return "\n".join(f"- {i.get(key)} — {i.get(count_key)}" for i in items) or "- (none)"

        categories = "\n".join(f"- {k}: {v}" for k, v in trend.category_distribution.items()) or "- (none)"
        flaky = "\n".join(f"- {f.get('test')} ({f.get('confidence')}%)" for f in trend.flaky_tests) or "- (none)"
        return (
            "# AI Quality Trend & Release Readiness\n\n"
            f"## Release Readiness\n"
            f"- **Score:** {readiness.score}/100\n"
            f"- **Risk:** {readiness.risk}\n"
            f"- **Recommendation:** {readiness.recommendation}\n"
            + "".join(f"  - {r}\n" for r in readiness.rationale)
            + f"\n## Summary\n- Total failures analysed: {trend.total_failures}\n"
            f"- Average runtime: {trend.average_runtime_s or 'n/a'} s\n\n"
            f"## Failure Categories\n{categories}\n\n"
            f"## Most Common Failures\n{_rows(trend.most_common_failures, 'test')}\n\n"
            f"## Most Failing APIs\n{_rows(trend.most_failing_apis, 'endpoint')}\n\n"
            f"## Most Failing Widgets\n{_rows(trend.most_failing_widgets, 'widget')}\n\n"
            f"## Flaky Tests\n{flaky}\n\n"
            f"## Failure Trend (by day)\n"
            + ("\n".join(f"- {day}: {n}" for day, n in trend.failure_trend.items()) or "- (none)")
            + "\n"
        )

    def save_trend(self, trend: TrendReport, readiness: ReleaseReadiness, stem: str = "trend") -> dict[str, Path]:
        self.cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        variants = {
            "md": self.trend_markdown(trend, readiness),
            "json": json.dumps(
                {"trend": trend.to_dict(), "release_readiness": readiness.to_dict()},
                indent=2,
                ensure_ascii=False,
            ),
        }
        paths: dict[str, Path] = {}
        for ext, content in variants.items():
            path = self.cfg.reports_dir / f"{stem}.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write trend report %s: %s", path, exc)
        return paths
