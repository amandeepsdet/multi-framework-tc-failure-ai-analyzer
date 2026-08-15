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
        category_label = escape(rc.category.value) + (
            f" / {escape(rc.subcategory)}" if rc.subcategory else ""
        )
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
        reasoning_block = self._reasoning_html(result)
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>AI Failure Analysis — {title}</title>
<style>
 body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem;color:#1f2933;}}
 .badge{{display:inline-block;padding:.2rem .6rem;border-radius:.4rem;background:#e4e7eb;margin-right:.4rem;}}
 h1{{font-size:1.4rem;}} h2{{font-size:1.1rem;margin-top:1.4rem;}}
 code,pre{{background:#f5f7fa;border-radius:.3rem;padding:.1rem .3rem;}}
 .reasoning{{border:1px solid #e4e7eb;border-radius:.6rem;padding:1rem 1.2rem;margin-top:1rem;background:#fafbfc;}}
 .conf{{display:inline-block;padding:.25rem .7rem;border-radius:.5rem;font-weight:600;color:#fff;}}
 .conf.high{{background:#0b8a3d;}} .conf.medium{{background:#c07d00;}} .conf.low{{background:#c0392b;}}
 .reasoning ul{{margin:.5rem 0;}} .reasoning .ok::marker{{color:#0b8a3d;}}
 .reasoning .warn{{color:#c0392b;}} .assess{{margin-top:.6rem;font-style:italic;}}
</style></head><body>
<h1>AI Failure Analysis — {title}</h1>
<p>
 <span class="badge">Category: {category_label}</span>
 <span class="badge">Confidence: {result.confidence.value}%</span>
 <span class="badge">Severity: {escape(result.severity.value)}</span>
 <span class="badge">Risk: {escape(result.risk_level or 'n/a')}</span>
 <span class="badge">Owner: {escape(result.owner)}</span>
 <span class="badge">Source: {escape(result.source)}</span>
</p>
<h2>Root cause</h2><p>{escape(rc.summary)}</p>
{f'<p>{escape(rc.detail)}</p>' if rc.detail else ''}
{reasoning_block}
<h2>Evidence</h2><ul>{evidence or '<li>None</li>'}</ul>
<h2>Recommendations</h2><ul>{recs or '<li>None</li>'}</ul>
{f'<h2>Similar past failures</h2><ul>{similar}</ul>' if similar else ''}
{f'<h2>Reasoning</h2><p>{escape(result.reasoning)}</p>' if result.reasoning else ''}
</body></html>
"""

    @staticmethod
    def _reasoning_html(result: AnalysisResult) -> str:
        cr = result.reasoning_detail
        if cr is None:
            return ""
        cls = cr.level.lower()
        points = "".join(f'<li class="ok">{escape(p)}</li>' for p in cr.reasoning_points)
        conflicts = ""
        if cr.conflicting_evidence:
            items = "".join(f"<li>{escape(c)}</li>" for c in cr.conflicting_evidence)
            conflicts = f'<p class="warn"><strong>Conflicting / missing signals:</strong></p><ul>{items}</ul>'
        used = ""
        if cr.supporting_evidence:
            used = (
                f'<p><small>Evidence used: {escape(", ".join(cr.supporting_evidence))}</small></p>'
            )
        low = (
            f'<p class="warn">{escape(cr.low_confidence_note)}</p>'
            if cr.low_confidence_note
            else ""
        )
        assess = f'<p class="assess">{escape(cr.assessment)}</p>' if cr.assessment else ""
        return (
            '<div class="reasoning"><h2>AI Confidence Reasoning</h2>'
            f'<p><span class="conf {cls}">{escape(cr.badge)} — {cr.confidence}%</span></p>'
            f"<ul>{points}</ul>{conflicts}{used}{low}{assess}</div>"
        )
