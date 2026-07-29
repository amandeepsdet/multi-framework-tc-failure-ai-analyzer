"""HTML reporter (self-contained, no external assets)."""

from __future__ import annotations

from html import escape

from ..core.interfaces import Reporter
from ..core.models import AnalysisResult, FailureContext
from .base import register_reporter


@register_reporter
class HTMLReporter(Reporter):
    format = "html"

    def render(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        rc = result.root_cause
        title = escape(context.test_name if context else "test")
        evidence = "".join(f"<li>{escape(e)}</li>" for e in result.evidence)
        recs = "".join(
            f"<li><strong>{escape(r.action)}</strong>"
            + (f" — {escape(r.rationale)}" if r.rationale else "")
            + "</li>"
            for r in result.recommendations
        )
        similar = "".join(
            f"<li>{escape(s.test_name)} ({escape(s.category)}, {s.similarity}%)</li>"
            for s in result.similar_failures
        )
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>AI Failure Analysis — {title}</title>
<style>
 body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem;color:#1f2933;}}
 .badge{{display:inline-block;padding:.2rem .6rem;border-radius:.4rem;background:#e4e7eb;margin-right:.4rem;}}
 h1{{font-size:1.4rem;}} h2{{font-size:1.1rem;margin-top:1.4rem;}}
 code,pre{{background:#f5f7fa;border-radius:.3rem;padding:.1rem .3rem;}}
</style></head><body>
<h1>AI Failure Analysis — {title}</h1>
<p>
 <span class="badge">Category: {escape(rc.category.value)}</span>
 <span class="badge">Confidence: {result.confidence.value}%</span>
 <span class="badge">Severity: {escape(result.severity.value)}</span>
 <span class="badge">Owner: {escape(result.owner)}</span>
 <span class="badge">Source: {escape(result.source)}</span>
</p>
<h2>Root cause</h2><p>{escape(rc.summary)}</p>
{f'<p>{escape(rc.detail)}</p>' if rc.detail else ''}
<h2>Evidence</h2><ul>{evidence or '<li>None</li>'}</ul>
<h2>Recommendations</h2><ul>{recs or '<li>None</li>'}</ul>
{f'<h2>Similar past failures</h2><ul>{similar}</ul>' if similar else ''}
{f'<h2>Reasoning</h2><p>{escape(result.reasoning)}</p>' if result.reasoning else ''}
</body></html>
"""
