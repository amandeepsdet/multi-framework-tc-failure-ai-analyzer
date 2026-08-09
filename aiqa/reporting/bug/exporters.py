"""Export a :class:`BugReport` to many tracker formats.

Supported: Markdown, HTML, JSON, plain text, Jira, Azure DevOps, GitHub Issues,
Linear. Each exporter is a small, single-responsibility function; ``export_all``
writes the canonical file set (bug.md, bug.html, bug.json, jira.json,
azure_work_item.json, github_issue.md) to a directory.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from ...core.models import BugReport


class BugExporter:
    """Renders a :class:`BugReport` into tracker-ready formats."""

    # -- Markdown ----------------------------------------------------------- #
    def to_markdown(self, bug: BugReport) -> str:
        lines = [
            f"# {bug.title}",
            "",
            f"> {bug.summary}" if bug.summary else "",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Category | {bug.category}"
            + (f" / {bug.subcategory}" if bug.subcategory else "") + " |",
            f"| Severity | {bug.severity} |",
            f"| Priority | {bug.priority} |",
            f"| Risk | {bug.risk or 'n/a'} |",
            f"| Confidence | {bug.confidence}% |",
            f"| Owner | {bug.owner} |",
            f"| Environment | {bug.environment or 'n/a'} |",
            f"| Framework | {bug.framework or 'n/a'} |",
            f"| Browser | {bug.browser or 'n/a'} |",
            f"| OS | {bug.os or 'n/a'} |",
            f"| Python | {bug.python_version or 'n/a'} |",
            f"| Build | {bug.build or 'n/a'} |",
            f"| Commit | {bug.commit or 'n/a'} |",
            "",
            "## Description",
            bug.description or "_n/a_",
            "",
            "## Steps to reproduce",
        ]
        lines += [f"{i}. {s}" for i, s in enumerate(bug.steps, 1)]
        lines += [
            "",
            f"**Expected:** {bug.expected}",
            f"**Actual:** {bug.actual}",
            "",
            "## Root cause",
            bug.root_cause or "_n/a_",
        ]
        if bug.ai_explanation:
            lines += ["", "## AI explanation", bug.ai_explanation]
        if bug.suggested_fix:
            lines += ["", "## Suggested fix", bug.suggested_fix]
        if bug.preventive_action:
            lines += ["", "## Preventive action", bug.preventive_action]
        lines += self._evidence_md(bug)
        return "\n".join(l for l in lines if l is not None) + "\n"

    @staticmethod
    def _evidence_md(bug: BugReport) -> list[str]:
        out: list[str] = []
        if bug.evidence:
            out += ["", "## Evidence"] + [f"- {e}" for e in bug.evidence]
        if bug.screenshots:
            out += ["", "### Screenshots"] + [f"- {s}" for s in bug.screenshots]
        if bug.network:
            out += ["", "### Network"] + [f"- `{n}`" for n in bug.network]
        if bug.logs:
            out += ["", "### Logs"] + [f"- `{l}`" for l in bug.logs]
        if bug.stacktrace:
            out += ["", "### Stacktrace", "```", bug.stacktrace.strip(), "```"]
        return out

    # -- Plain text --------------------------------------------------------- #
    def to_plaintext(self, bug: BugReport) -> str:
        md = self.to_markdown(bug)
        # Strip lightweight markdown decorations for a clean text export.
        for token in ("### ", "## ", "# ", "**", "`", "> ", "| "):
            md = md.replace(token, "")
        return md

    # -- JSON --------------------------------------------------------------- #
    def to_json(self, bug: BugReport) -> str:
        return bug.to_json()

    # -- HTML --------------------------------------------------------------- #
    def to_html(self, bug: BugReport) -> str:
        def li(items: list[str]) -> str:
            return "".join(f"<li>{escape(str(i))}</li>" for i in items)

        rows = "".join(
            f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>"
            for k, v in [
                ("Category", bug.category + (f" / {bug.subcategory}" if bug.subcategory else "")),
                ("Severity", bug.severity), ("Priority", bug.priority),
                ("Risk", bug.risk or "n/a"), ("Confidence", f"{bug.confidence}%"),
                ("Owner", bug.owner), ("Environment", bug.environment or "n/a"),
                ("Framework", bug.framework or "n/a"), ("Browser", bug.browser or "n/a"),
                ("OS", bug.os or "n/a"), ("Python", bug.python_version or "n/a"),
                ("Build", bug.build or "n/a"), ("Commit", bug.commit or "n/a"),
            ]
        )
        stack = (f"<h2>Stacktrace</h2><pre>{escape(bug.stacktrace.strip())}</pre>"
                 if bug.stacktrace else "")
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(bug.title)}</title>
<style>
 body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem;color:#1f2933;}}
 table{{border-collapse:collapse;margin:1rem 0;}} th,td{{border:1px solid #e4e7eb;padding:.3rem .6rem;text-align:left;}}
 th{{background:#f5f7fa;}} pre{{background:#f5f7fa;padding:1rem;border-radius:.4rem;overflow:auto;}}
 h1{{font-size:1.35rem;}} h2{{font-size:1.05rem;margin-top:1.2rem;}}
</style></head><body>
<h1>{escape(bug.title)}</h1>
<p>{escape(bug.summary)}</p>
<table>{rows}</table>
<h2>Description</h2><p>{escape(bug.description)}</p>
<h2>Steps to reproduce</h2><ol>{li(bug.steps)}</ol>
<p><strong>Expected:</strong> {escape(bug.expected)}<br>
<strong>Actual:</strong> {escape(bug.actual)}</p>
<h2>Root cause</h2><p>{escape(bug.root_cause)}</p>
{f'<h2>AI explanation</h2><p>{escape(bug.ai_explanation)}</p>' if bug.ai_explanation else ''}
{f'<h2>Suggested fix</h2><p>{escape(bug.suggested_fix)}</p>' if bug.suggested_fix else ''}
{f'<h2>Preventive action</h2><p>{escape(bug.preventive_action)}</p>' if bug.preventive_action else ''}
{f'<h2>Evidence</h2><ul>{li(bug.evidence)}</ul>' if bug.evidence else ''}
{f'<h2>Screenshots</h2><ul>{li(bug.screenshots)}</ul>' if bug.screenshots else ''}
{f'<h2>Network</h2><ul>{li(bug.network)}</ul>' if bug.network else ''}
{f'<h2>Logs</h2><ul>{li(bug.logs)}</ul>' if bug.logs else ''}
{stack}
</body></html>
"""

    # -- Jira --------------------------------------------------------------- #
    def to_jira(self, bug: BugReport) -> dict[str, Any]:
        labels = [bug.category.replace(" ", "-").lower()]
        if bug.subcategory:
            labels.append(bug.subcategory.replace(" ", "-").lower())
        return {
            "fields": {
                "summary": bug.title,
                "issuetype": {"name": "Bug"},
                "priority": {"name": self._jira_priority(bug.priority)},
                "labels": labels,
                "description": self.to_plaintext(bug),
            }
        }

    @staticmethod
    def _jira_priority(priority: str) -> str:
        return {"P0": "Highest", "P1": "High", "P2": "Medium",
                "P3": "Low", "P4": "Lowest"}.get(priority, "Medium")

    def to_jira_json(self, bug: BugReport) -> str:
        return json.dumps(self.to_jira(bug), indent=2, ensure_ascii=False)

    # -- Azure DevOps ------------------------------------------------------- #
    def to_azure(self, bug: BugReport) -> list[dict[str, Any]]:
        def op(path: str, value: Any) -> dict[str, Any]:
            return {"op": "add", "path": path, "value": value}

        return [
            op("/fields/System.Title", bug.title),
            op("/fields/System.WorkItemType", "Bug"),
            op("/fields/Microsoft.VSTS.Common.Priority", self._azure_priority(bug.priority)),
            op("/fields/Microsoft.VSTS.Common.Severity", self._azure_severity(bug.severity)),
            op("/fields/System.AssignedTo", bug.owner),
            op("/fields/System.Tags", f"{bug.category}; {bug.subcategory}".strip("; ")),
            op("/fields/Microsoft.VSTS.TCM.ReproSteps", self.to_html(bug)),
        ]

    @staticmethod
    def _azure_priority(priority: str) -> int:
        return {"P0": 1, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(priority, 2)

    @staticmethod
    def _azure_severity(severity: str) -> str:
        return {"Blocker": "1 - Critical", "Critical": "1 - Critical",
                "Major": "2 - High", "Minor": "3 - Medium",
                "Trivial": "4 - Low"}.get(severity, "2 - High")

    def to_azure_json(self, bug: BugReport) -> str:
        return json.dumps(self.to_azure(bug), indent=2, ensure_ascii=False)

    # -- GitHub Issues ------------------------------------------------------ #
    def to_github(self, bug: BugReport) -> dict[str, Any]:
        labels = ["bug", bug.category.replace(" ", "-").lower()]
        return {"title": bug.title, "body": self.to_markdown(bug), "labels": labels}

    def to_github_issue(self, bug: BugReport) -> str:
        # Human-readable markdown file with a title header.
        return self.to_markdown(bug)

    # -- Linear ------------------------------------------------------------- #
    def to_linear(self, bug: BugReport) -> dict[str, Any]:
        return {
            "title": bug.title,
            "description": self.to_markdown(bug),
            "priority": self._linear_priority(bug.priority),
            "labels": [bug.category, bug.subcategory] if bug.subcategory else [bug.category],
        }

    @staticmethod
    def _linear_priority(priority: str) -> int:
        # Linear: 1 Urgent .. 4 Low, 0 None
        return {"P0": 1, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(priority, 2)

    def to_linear_json(self, bug: BugReport) -> str:
        return json.dumps(self.to_linear(bug), indent=2, ensure_ascii=False)

    # -- Bulk file export --------------------------------------------------- #
    def export_all(self, bug: BugReport, out_dir: str | Path) -> dict[str, Path]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        files = {
            "bug.md": self.to_markdown(bug),
            "bug.html": self.to_html(bug),
            "bug.json": self.to_json(bug),
            "bug.txt": self.to_plaintext(bug),
            "jira.json": self.to_jira_json(bug),
            "azure_work_item.json": self.to_azure_json(bug),
            "github_issue.md": self.to_github_issue(bug),
            "linear.json": self.to_linear_json(bug),
        }
        written: dict[str, Path] = {}
        for name, content in files.items():
            path = out / name
            path.write_text(content, encoding="utf-8")
            written[name] = path
        return written
