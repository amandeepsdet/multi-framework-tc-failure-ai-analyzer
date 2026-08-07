"""Prompt construction from external, reusable templates.

Prompts are **not** hardcoded — they live as ``.txt`` files under ``prompts/``
and use ``{{TOKEN}}`` placeholders. Double-brace tokens avoid clashing with the
JSON braces that appear inside the prompt bodies, so templates can freely show
example JSON. Unknown tokens are left untouched and missing context keys render
as empty strings, so a template never crashes a run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config

logger = get_logger("ai.prompt_builder")

_TOKEN_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

# Built-in fallbacks so the engine works even if a prompt file is missing.
_DEFAULT_TEMPLATES: dict[str, str] = {
    "root_cause": (
        "You are a senior QA reliability engineer performing root-cause analysis "
        "on an automated test failure. Use ONLY the evidence provided; never "
        "invent facts. Every claim in 'evidence' must be traceable to the inputs.\n\n"
        "TEST: {{TEST_NAME}}\n"
        "EXCEPTION: {{EXCEPTION_TYPE}}: {{EXCEPTION_MESSAGE}}\n"
        "ASSERTION: {{ASSERTION_MESSAGE}}\n"
        "URL: {{URL}}\nPAGE TITLE: {{PAGE_TITLE}}\n"
        "STACKTRACE:\n{{STACKTRACE}}\n\n"
        "CONSOLE LOGS:\n{{CONSOLE_LOGS}}\n\n"
        "NETWORK:\n{{NETWORK}}\n\n"
        "API RESPONSES:\n{{API_RESPONSES}}\n\n"
        "DOM (truncated):\n{{DOM}}\n\n"
        "SIMILAR PAST FAILURES:\n{{SIMILAR_FAILURES}}\n\n"
        "FRAMEWORK CONTEXT:\n{{FRAMEWORK_CONTEXT}}\n\n"
        "Respond with ONLY a JSON object of the form:\n"
        '{"root_cause": "...", "category": "one of '
        "[UI, Backend, API, Authentication, Authorization, Locator, Network, "
        "Performance, Infrastructure, Browser, Environment, Data, Configuration, "
        'Flaky Test, Unknown]", "confidence": 0-100, "severity": '
        '"Blocker|Critical|Major|Minor|Trivial", "owner": "team/role", '
        '"evidence": ["fact referencing the inputs", ...], '
        '"recommended_fix": "...", "reasoning": "..."}'
    ),
    "bug_report": (
        "Generate a professional bug report from the failure analysis below. "
        "Base every section strictly on the provided evidence.\n\n"
        "TEST: {{TEST_NAME}}\nCATEGORY: {{CATEGORY}}\nROOT CAUSE: {{ROOT_CAUSE}}\n"
        "SEVERITY: {{SEVERITY}}\nENVIRONMENT: {{ENVIRONMENT}}\n"
        "EVIDENCE:\n{{EVIDENCE}}\nRECOMMENDED FIX: {{RECOMMENDED_FIX}}\n\n"
        "Respond with ONLY JSON: {\"title\":\"\",\"description\":\"\","
        "\"steps\":[],\"expected\":\"\",\"actual\":\"\",\"severity\":\"\","
        "\"priority\":\"P1|P2|P3\",\"owner\":\"\",\"suggested_fix\":\"\"}"
    ),
    "release_summary": (
        "You are a release manager. Given the aggregated failure statistics "
        "below, write a concise, executive release-readiness summary.\n\n"
        "STATS:\n{{STATS}}\n\nRespond in plain markdown."
    ),
    "flaky_analysis": (
        "Analyse the following test execution history and identify flaky tests "
        "(intermittent pass/fail with no code change). Use only the data given.\n\n"
        "HISTORY:\n{{HISTORY}}\n\nRespond with ONLY JSON: "
        "{\"flaky_tests\":[{\"test\":\"\",\"reason\":\"\",\"confidence\":0}]}"
    ),
    "locator_analysis": (
        "A Playwright locator failed. Compare the expected locator against the "
        "current DOM and suggest the most likely correct replacement.\n\n"
        "EXPECTED LOCATOR: {{EXPECTED_LOCATOR}}\n\nDOM (truncated):\n{{DOM}}\n\n"
        "Respond with ONLY JSON: {\"suggestions\":[{\"locator\":\"\","
        "\"similarity\":0-100,\"rationale\":\"\"}]}"
    ),
    "visual_analysis": (
        "Inspect the attached screenshot of a web dashboard under test and "
        "answer strictly from what is visible: Is a UI element missing? Is a loading "
        "spinner visible? Is the dashboard blank? Is the layout broken? Is an "
        "authentication/login page shown? Respond with ONLY JSON: "
        "{\"widget_missing\":bool,\"spinner_visible\":bool,\"dashboard_blank\":bool,"
        "\"layout_broken\":bool,\"auth_page_shown\":bool,\"summary\":\"\"}"
    ),
}


class PromptBuilder:
    """Loads templates from disk (with in-code fallbacks) and injects context."""

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg
        self.dir = cfg.prompts_dir

    def load_template(self, name: str) -> str:
        """Return the raw template text for ``name`` (without extension)."""
        path = self.dir / f"{name}.txt"
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not read prompt '%s': %s", name, exc)
        if name in _DEFAULT_TEMPLATES:
            return _DEFAULT_TEMPLATES[name]
        raise FileNotFoundError(f"No prompt template named '{name}'")

    def build(self, name: str, context: dict[str, Any]) -> str:
        """Render template ``name`` by substituting ``{{TOKEN}}`` placeholders."""
        template = self.load_template(name)
        upper = {k.upper(): _stringify(v) for k, v in context.items()}

        def _replace(match: re.Match[str]) -> str:
            token = match.group(1).upper()
            return upper.get(token, match.group(0))

        return _TOKEN_RE.sub(_replace, template)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    import json

    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)
