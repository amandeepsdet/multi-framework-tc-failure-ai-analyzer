"""ExecutionReportBuilder — assembles and renders ONE report per execution.

Responsibilities:
* accumulate the analysed failures / passes / skips of a single run;
* build an :class:`ExecutionRun` aggregate;
* render exactly one ``ai_report.html`` plus ``report.json``, ``report.md`` and
  ``execution_summary.json`` into the run's own folder, copying screenshots and
  attachments alongside.

It does NOT invent analysis: it consumes the :class:`AnalysisResult` objects the
engine already produced. There is never one HTML file per test case.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from ...core.models import AnalysisResult, FailureContext
from ..bug_report import BugReportBuilder
from ..markdown import MarkdownReporter
from .assets import BASE_CSS, THEME_JS
from .clustering import FailureClusterer
from .comparison import RunComparison
from .knowledge_base import FailureMemory
from .models import ExecutionRun, RunFailure, utc_now_iso

_SEVERITY_CLASS = {
    "Blocker": "b-bad", "Critical": "b-bad", "Major": "b-warn",
    "Minor": "b-info", "Trivial": "b-muted",
}
_HEALTH_CLASS = {"Healthy": "b-ok", "Warning": "b-warn", "Critical": "b-bad"}
_BAND_CLASS = {"Excellent": "b-ok", "Good": "b-ok", "Warning": "b-warn", "Poor": "b-bad"}
_READY_CLASS = {"READY": "b-ok", "AT RISK": "b-warn", "NOT READY": "b-bad"}


class ExecutionReportBuilder:
    """Accumulates a run's results and renders its self-contained report."""

    def __init__(self, run_dir: Path | str, run_id: str):
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self._run = ExecutionRun(run_id=run_id)
        self._pairs: list[tuple[RunFailure, AnalysisResult, FailureContext | None]] = []
        self._start = datetime.now(timezone.utc)

    # -- lifecycle ---------------------------------------------------------- #
    def begin(
        self,
        *,
        run_name: str = "",
        framework: str = "",
        environment: str = "",
        browser: str = "",
        os: str = "",
        python_version: str = "",
        package_version: str = "",
        commit: str = "",
    ) -> None:
        self._start = datetime.now(timezone.utc)
        r = self._run
        r.run_name = run_name or self.run_id
        r.started = self._start.isoformat()
        r.framework = framework
        r.environment = environment
        r.browser = browser
        r.os = os
        r.python_version = python_version
        r.package_version = package_version
        r.commit = commit

    def add_failure(self, result: AnalysisResult, context: FailureContext | None = None) -> RunFailure:
        failure = RunFailure.from_analysis(result, context)
        # Inherit run-level metadata when the context omits it.
        failure.framework = failure.framework or self._run.framework
        failure.environment = failure.environment or self._run.environment
        failure.browser = failure.browser or self._run.browser
        self._pairs.append((failure, result, context))
        self._run.failures.append(failure)
        self._run.failed += 1
        self._run.total += 1
        return failure

    def add_success(self, test_id: str = "") -> None:
        self._run.passed += 1
        self._run.total += 1

    def add_skipped(self, test_id: str = "") -> None:
        self._run.skipped += 1
        self._run.total += 1

    @property
    def has_data(self) -> bool:
        return self._run.total > 0

    def build_execution_run(self) -> ExecutionRun:
        r = self._run
        r.finished = utc_now_iso()
        r.duration_s = round((datetime.now(timezone.utc) - self._start).total_seconds(), 2)
        r.recompute_aggregates()
        r.report_rel = f"{self.run_id}/ai_report.html"
        return r

    # -- rendering ---------------------------------------------------------- #
    def render(
        self,
        run: ExecutionRun,
        comparison: RunComparison | None = None,
        memories: dict[str, FailureMemory] | None = None,
    ) -> dict[str, str]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "screenshots").mkdir(exist_ok=True)
        (self.run_dir / "attachments").mkdir(exist_ok=True)
        (self.run_dir / "charts").mkdir(exist_ok=True)

        self._copy_artifacts(run)
        memories = memories or {}

        html = self._render_html(run, comparison, memories)
        md = self._render_markdown(run)
        report_json = json.dumps(run.to_dict(), indent=2, ensure_ascii=False)
        exec_json = json.dumps(run.to_dict(), indent=2, ensure_ascii=False)
        charts_json = json.dumps(self._charts_payload(run), indent=2, ensure_ascii=False)

        paths = {
            "html": self.run_dir / "ai_report.html",
            "json": self.run_dir / "report.json",
            "md": self.run_dir / "report.md",
            "summary": self.run_dir / "execution_summary.json",
            "charts": self.run_dir / "charts" / "charts.json",
        }
        paths["html"].write_text(html, encoding="utf-8")
        paths["json"].write_text(report_json, encoding="utf-8")
        paths["md"].write_text(md, encoding="utf-8")
        paths["summary"].write_text(exec_json, encoding="utf-8")
        paths["charts"].write_text(charts_json, encoding="utf-8")
        return {k: str(v) for k, v in paths.items()}

    # -- artifact copying --------------------------------------------------- #
    def _copy_artifacts(self, run: ExecutionRun) -> None:
        for f in run.failures:
            if f.screenshot and not f.screenshot.startswith(("data:", "http")):
                src = Path(f.screenshot)
                if src.exists() and src.is_file():
                    dest = self.run_dir / "screenshots" / src.name
                    try:
                        shutil.copy2(src, dest)
                        f.screenshot = f"screenshots/{src.name}"
                    except OSError:
                        pass
            new_attach: dict[str, str] = {}
            for name, path in f.attachments.items():
                src = Path(path)
                if src.exists() and src.is_file():
                    dest = self.run_dir / "attachments" / src.name
                    try:
                        shutil.copy2(src, dest)
                        new_attach[name] = f"attachments/{src.name}"
                        continue
                    except OSError:
                        pass
                new_attach[name] = path
            f.attachments = new_attach

    def _charts_payload(self, run: ExecutionRun) -> dict[str, Any]:
        clusters = FailureClusterer().cluster(run.failures)
        return {
            "categories": run.categories,
            "severities": run.severities,
            "owners": run.owners,
            "clusters": [c.to_dict() for c in clusters],
        }

    # -- markdown ----------------------------------------------------------- #
    def _render_markdown(self, run: ExecutionRun) -> str:
        md_reporter = MarkdownReporter()
        lines = [
            f"# Execution Report — {run.run_id}",
            "",
            run.executive_summary or "",
            "",
            f"- **Framework:** {run.framework or 'n/a'}",
            f"- **Environment:** {run.environment or 'n/a'}",
            f"- **Total:** {run.total}  |  **Passed:** {run.passed}  |  "
            f"**Failed:** {run.failed}  |  **Skipped:** {run.skipped}",
            f"- **Pass rate:** {run.pass_rate:.0f}%  |  **Quality score:** "
            f"{run.quality_score}/100 ({run.quality_band})",
            f"- **Build health:** {run.build_health}  |  **Release readiness:** {run.release_readiness}",
            "",
        ]
        for i, (_f, result, context) in enumerate(self._pairs, 1):
            lines.append(f"## {i}. {result.root_cause.summary or 'Failure'}")
            lines.append("")
            lines.append(md_reporter.render(result, context))
        return "\n".join(lines) + "\n"

    # -- html --------------------------------------------------------------- #
    def _render_html(
        self,
        run: ExecutionRun,
        comparison: RunComparison | None,
        memories: dict[str, FailureMemory],
    ) -> str:
        nav = self._nav_html(run)
        kpis = self._kpi_html(run)
        summary = self._summary_html(run)
        charts = self._charts_html(run)
        compare = self._comparison_html(comparison)
        failures = "".join(
            self._failure_html(f, result, context, i, memories.get(f.signature))
            for i, (f, result, context) in enumerate(self._pairs, 1)
        ) or "<div class='card'>No failures in this execution.</div>"

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="light"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Execution Report — {escape(run.run_id)}</title>
<style>{BASE_CSS}</style></head><body>
<div class="app">
<aside class="side">
  <div class="brand"><span class="dot"></span> Quality Intelligence</div>
  <a class="btn" href="../index.html">← Back to Dashboard</a>
  <input id="navSearch" class="input" style="margin:12px 0" placeholder="Search failures…"
    oninput="filterNav(this.value)">
  <h2 style="margin-top:6px">Failure Navigator</h2>
  <div id="navList">{nav or '<p class="muted">No failures.</p>'}</div>
</aside>
<main class="main">
  <div class="topbar">
    <div><h1>Execution Report</h1>
      <p class="sub">{escape(run.run_id)} · {escape(run.framework or 'suite')} · {escape(run.environment or 'default')}</p></div>
    <div class="chip-row">
      <button class="btn" onclick="expandAll(true)">Expand All</button>
      <button class="btn" onclick="expandAll(false)">Collapse All</button>
      <button class="btn" onclick="toggleTheme()">Theme</button>
      <button class="btn" onclick="window.print()">Print</button>
    </div>
  </div>
  {summary}
  <div class="grid kpis">{kpis}</div>
  {compare}
  {charts}
  <h2>Failure Analysis</h2>
  {failures}
  <div class="footer">Generated by AIQA · Quality Intelligence Platform</div>
</main>
</div>
<script>{THEME_JS}</script>
<script>
function filterNav(q){{
  q=(q||'').toLowerCase();
  document.querySelectorAll('#navList .nav-item').forEach(function(n){{
    n.classList.toggle('hidden', q && n.getAttribute('data-search').indexOf(q)<0);
  }});
}}
function expandAll(open){{
  document.querySelectorAll('.accordion').forEach(function(a){{a.classList.toggle('open',open);}});
}}
function goTo(id){{
  var el=document.getElementById(id);if(!el)return;
  el.classList.add('open');el.scrollIntoView({{behavior:'smooth',block:'start'}});
}}
</script>
</body></html>
"""

    def _nav_html(self, run: ExecutionRun) -> str:
        rows = []
        for i, f in enumerate(run.failures, 1):
            sev_cls = _SEVERITY_CLASS.get(f.severity, "b-muted")
            search = escape(f"{f.test_name} {f.category} {f.owner} {f.severity}".lower(), quote=True)
            rows.append(
                f"<a class='nav-item' data-search='{search}' onclick=\"goTo('fail-{i}')\">"
                f"<div class='tname'>✗ {escape(f.test_name)}</div>"
                f"<div class='meta'>"
                f"<span class='badge {sev_cls}'>{escape(f.severity)}</span>"
                f"<span class='badge b-info'>{f.confidence}%</span>"
                f"<span class='badge b-muted'>{escape(f.category)}</span>"
                f"</div>"
                f"<div class='muted' style='margin-top:4px;font-size:11px'>{escape(f.owner)}</div>"
                f"</a>"
            )
        return "".join(rows)

    def _kpi_html(self, run: ExecutionRun) -> str:
        def kpi(label, value, sub=""):
            s = f" <small>{escape(str(sub))}</small>" if sub else ""
            return (f"<div class='card kpi'><div class='label'>{escape(label)}</div>"
                    f"<div class='value'>{escape(str(value))}{s}</div></div>")
        return "".join([
            kpi("Total", run.total),
            kpi("Passed", run.passed),
            kpi("Failed", run.failed),
            kpi("Skipped", run.skipped),
            kpi("Pass Rate", f"{run.pass_rate:.0f}", "%"),
            kpi("Critical", run.critical_count),
            kpi("Avg Confidence", f"{run.avg_confidence:.0f}", "%"),
            kpi("Duration", f"{run.duration_s:.0f}", "s"),
        ])

    def _summary_html(self, run: ExecutionRun) -> str:
        band_cls = _BAND_CLASS.get(run.quality_band, "b-muted")
        health_cls = _HEALTH_CLASS.get(run.build_health, "b-muted")
        ready_cls = _READY_CLASS.get(run.release_readiness, "b-muted")
        return f"""
<div class="grid cards">
  <div class="card">
    <h2 style="margin-top:0">AI Executive Summary</h2>
    <p>{escape(run.executive_summary or 'No summary available.')}</p>
  </div>
  <div class="card">
    <h2 style="margin-top:0">Quality Score</h2>
    <div class="gauge">{run.quality_score}<small class="muted">/100</small></div>
    <div class="progress" style="margin:10px 0"><span style="width:{run.quality_score}%"></span></div>
    <div class="chip-row">
      <span class="badge {band_cls}">{escape(run.quality_band)}</span>
      <span class="badge {health_cls}">Build: {escape(run.build_health)}</span>
      <span class="badge {ready_cls}">Release: {escape(run.release_readiness)}</span>
    </div>
  </div>
</div>"""

    def _charts_html(self, run: ExecutionRun) -> str:
        if not run.failures:
            return ""
        cat = self._bar_block("Failures by Category", run.categories)
        sev = self._bar_block("Failures by Severity", run.severities)
        owner = self._bar_block("Failures by Owner", run.owners)
        clusters = FailureClusterer().cluster(run.failures)
        cluster_map = {c.name: c.count for c in clusters}
        cluster_block = self._bar_block("Failure Clusters", cluster_map)
        return f"""<h2>Execution Insights</h2>
<div class="grid cards">
  <div class="card">{cat}</div>
  <div class="card">{sev}</div>
  <div class="card">{owner}</div>
  <div class="card">{cluster_block}</div>
</div>"""

    @staticmethod
    def _bar_block(title: str, data: dict[str, int]) -> str:
        if not data:
            return f"<h2 style='margin-top:0'>{escape(title)}</h2><p class='muted'>No data.</p>"
        total = max(data.values()) or 1
        rows = []
        for label, n in data.items():
            pct = round(100.0 * n / total)
            rows.append(
                f"<div class='row'><div>{escape(str(label))}</div>"
                f"<div class='track'><div class='fill' style='width:{pct}%'></div></div>"
                f"<div class='right'>{n}</div></div>"
            )
        return (f"<h2 style='margin-top:0'>{escape(title)}</h2>"
                f"<div class='bar-chart'>{''.join(rows)}</div>")

    def _comparison_html(self, comparison: RunComparison | None) -> str:
        if comparison is None or not comparison.previous_run_id:
            return ""
        c = comparison
        def delta(v, unit=""):
            sign = "+" if v > 0 else ""
            return f"{sign}{v}{unit}"
        return f"""<h2>Comparison vs {escape(c.previous_run_id)}</h2>
<div class="grid kpis">
  <div class="card kpi"><div class="label">New Failures</div><div class="value">{len(c.new_failures)}</div></div>
  <div class="card kpi"><div class="label">Resolved</div><div class="value">{len(c.resolved_failures)}</div></div>
  <div class="card kpi"><div class="label">Persisting</div><div class="value">{len(c.persisting_failures)}</div></div>
  <div class="card kpi"><div class="label">Regression</div><div class="value">{c.regression_pct:.0f}<small>%</small></div></div>
  <div class="card kpi"><div class="label">Pass Rate Δ</div><div class="value">{delta(c.pass_rate_change)}<small>pts</small></div></div>
  <div class="card kpi"><div class="label">Quality Δ</div><div class="value">{delta(c.quality_score_diff)}</div></div>
</div>"""

    def _failure_html(
        self,
        f: RunFailure,
        result: AnalysisResult,
        context: FailureContext | None,
        idx: int,
        memory: FailureMemory | None,
    ) -> str:
        sev_cls = _SEVERITY_CLASS.get(f.severity, "b-muted")
        bug = BugReportBuilder().build(result, context)
        bug_md = BugReportBuilder.to_markdown(bug)
        bug_json = json.dumps(bug.to_dict(), indent=2, ensure_ascii=False)
        jira = self._jira_text(f, bug)
        azure = self._azure_text(f, bug)

        evidence = "".join(f"<li>{escape(e)}</li>" for e in result.evidence) or "<li class='muted'>None</li>"
        recs = "".join(
            f"<li><strong>{escape(r.action)}</strong>"
            + (f" — {escape(r.rationale)}" if r.rationale else "") + "</li>"
            for r in result.recommendations
        ) or "<li class='muted'>None</li>"
        similar = "".join(
            f"<li>{escape(s.test_name)} — {escape(s.category)} ({s.similarity}% similar)</li>"
            for s in result.similar_failures
        )
        similar_block = f"<h2>Similar Past Failures</h2><ul class='clean'>{similar}</ul>" if similar else ""
        memory_block = self._memory_html(memory)
        screenshot_block = self._screenshot_html(f)

        return f"""
<div class="accordion" id="fail-{idx}">
  <div class="head" onclick="toggleAccordion(this)">
    <div><strong>✗ {escape(f.test_name)}</strong>
      <div class="muted" style="font-size:12px;margin-top:3px">{escape(f.root_cause[:120])}</div></div>
    <div class="chip-row">
      <span class="badge {sev_cls}">{escape(f.severity)}</span>
      <span class="badge b-info">{f.confidence}%</span>
      <span class="badge b-muted">{escape(f.category)}</span>
      <span class="badge b-muted">{escape(f.owner)}</span>
    </div>
  </div>
  <div class="body">
    <h2>AI Executive Summary</h2>
    <p>{escape(result.root_cause.summary)}</p>
    {f'<p class="muted">{escape(result.root_cause.detail)}</p>' if result.root_cause.detail else ''}
    {f'<pre>{escape(result.reasoning)}</pre>' if result.reasoning else ''}
    {memory_block}
    <h2>Evidence</h2><ul class="clean">{evidence}</ul>
    {screenshot_block}
    <h2>Suggested Fixes</h2><ul class="clean">{recs}</ul>
    {similar_block}
    <h2>Metadata</h2>
    <div class="meta-grid">
      <div class="m"><div class="k">Test ID</div><div class="v">{escape(f.test_id)}</div></div>
      <div class="m"><div class="k">Framework</div><div class="v">{escape(f.framework or 'n/a')}</div></div>
      <div class="m"><div class="k">Environment</div><div class="v">{escape(f.environment or 'n/a')}</div></div>
      <div class="m"><div class="k">Browser</div><div class="v">{escape(f.browser or 'n/a')}</div></div>
      <div class="m"><div class="k">Exception</div><div class="v">{escape(f.exception_type or 'n/a')}</div></div>
      <div class="m"><div class="k">HTTP</div><div class="v">{escape(', '.join(map(str,f.http_statuses)) or 'n/a')}</div></div>
      <div class="m"><div class="k">Signature</div><div class="v">{escape(f.signature)}</div></div>
      <div class="m"><div class="k">Source</div><div class="v">{escape(f.source)}</div></div>
    </div>
    <h2>Bug Report</h2>
    <div class="chip-row" style="margin-bottom:10px">
      <button class="btn primary" onclick="copyText('bugmd-{idx}',this)">Copy Bug</button>
      <button class="btn" onclick="downloadText('bugmd-{idx}','bug_{idx}.md')">Download MD</button>
      <button class="btn" onclick="downloadText('bugjson-{idx}','bug_{idx}.json')">Download JSON</button>
      <button class="btn" onclick="copyText('jira-{idx}',this)">Copy Jira</button>
      <button class="btn" onclick="copyText('azure-{idx}',this)">Copy Azure DevOps</button>
      <button class="btn" onclick="window.print()">Print</button>
    </div>
    <pre id="bugmd-{idx}">{escape(bug_md)}</pre>
    <pre id="bugjson-{idx}" class="hidden">{escape(bug_json)}</pre>
    <pre id="jira-{idx}" class="hidden">{escape(jira)}</pre>
    <pre id="azure-{idx}" class="hidden">{escape(azure)}</pre>
  </div>
</div>"""

    @staticmethod
    def _memory_html(memory: FailureMemory | None) -> str:
        if not memory or not memory.seen_before:
            return ""
        return f"""<h2>Failure Memory</h2>
<div class="meta-grid">
  <div class="m"><div class="k">Seen Before</div><div class="v">Yes</div></div>
  <div class="m"><div class="k">Occurrences</div><div class="v">{memory.occurrences}</div></div>
  <div class="m"><div class="k">Last Occurrence</div><div class="v">{escape(memory.last_occurrence)}</div></div>
  <div class="m"><div class="k">Avg Confidence</div><div class="v">{memory.avg_confidence:.0f}%</div></div>
  <div class="m"><div class="k">Owner</div><div class="v">{escape(memory.owner or 'n/a')}</div></div>
  <div class="m"><div class="k">Most Successful Fix</div><div class="v">{escape(memory.most_successful_fix or 'n/a')}</div></div>
</div>"""

    def _screenshot_html(self, f: RunFailure) -> str:
        if not f.screenshot:
            return ""
        return (f"<h2>Screenshot</h2><a href='{escape(f.screenshot)}' target='_blank'>"
                f"<img src='{escape(f.screenshot)}' alt='screenshot' "
                f"style='max-width:100%;border:1px solid var(--border);border-radius:10px'></a>")

    @staticmethod
    def _jira_text(f: RunFailure, bug) -> str:
        lines = [
            f"h2. {bug.title}",
            "",
            f"*Severity:* {bug.severity}  *Priority:* {bug.priority}  *Owner:* {bug.owner}",
            f"*Environment:* {bug.environment or 'n/a'}",
            "",
            "h3. Description",
            bug.description or "n/a",
            "",
            "h3. Steps to reproduce",
        ]
        lines += [f"# {s}" for s in bug.steps]
        lines += ["", f"*Expected:* {bug.expected}", f"*Actual:* {bug.actual}"]
        if bug.suggested_fix:
            lines += ["", "h3. Suggested fix", bug.suggested_fix]
        return "\n".join(lines)

    @staticmethod
    def _azure_text(f: RunFailure, bug) -> str:
        payload = {
            "op": "add",
            "workItemType": "Bug",
            "fields": {
                "System.Title": bug.title,
                "System.AssignedTo": bug.owner,
                "Microsoft.VSTS.Common.Severity": bug.severity,
                "Microsoft.VSTS.Common.Priority": bug.priority,
                "Microsoft.VSTS.TCM.ReproSteps": "<br>".join(
                    [bug.description] + [f"{i}. {s}" for i, s in enumerate(bug.steps, 1)]
                ),
                "System.Tags": f"{f.category};{f.framework}".strip(";"),
            },
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)
