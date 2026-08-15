"""Command-line interface for the framework-agnostic AIQA SDK.

Four subcommands surface the Phase 1 enterprise capabilities:

    aiqa classify        <context.json>          # intelligent failure classification
    aiqa explain-failure <context.json>          # full analysis + AI confidence reasoning
    aiqa heal-locator    --old <loc> --dom <html-file> [--text ...]
    aiqa generate-bug    <context.json> [--format md|html|json|jira|azure|github|linear]
                                         [--out <dir>]

``<context.json>`` is a serialized :class:`aiqa.FailureContext` (as produced by
``FailureContext.to_dict()`` / an adapter). Everything runs offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import FailureAnalyzer, FailureClassifier
from .core.models import FailureContext
from .healing import heal_locator
from .reporting import BugExporter, BugGenerationEngine, get_reporter


def _load_context(path: str) -> FailureContext:
    text = Path(path).read_text(encoding="utf-8")
    return FailureContext.from_json(text)


def _cmd_classify(args: argparse.Namespace) -> int:
    context = _load_context(args.context)
    result = FailureClassifier().classify(context)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Category   : {result.category.value} / {result.subcategory}")
        print(f"Confidence : {result.confidence}%")
        print(f"Risk       : {result.risk_level}")
        print(f"Owner      : {result.owner}")
        print(f"Reason     : {result.reason}")
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    context = _load_context(args.context)
    result = FailureAnalyzer().analyze(context)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(get_reporter("console").render(result, context))
    return 0


def _cmd_heal(args: argparse.Namespace) -> int:
    dom = Path(args.dom).read_text(encoding="utf-8") if args.dom else ""
    attrs = dict(kv.split("=", 1) for kv in (args.attr or []))
    result = heal_locator(args.old, dom, target_text=args.text, target_attributes=attrs or None)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    print(f"Old locator : {result.old_locator}")
    print(f"Diagnosis   : {result.failure_reason}")
    if not result.healed:
        print("No suggestions could be generated.")
        return 1
    for i, s in enumerate(result.suggestions):
        marker = "->" if i == 0 else "  "
        print(f"{marker} {s.strategy:8} {s.quality:5} {s.confidence:3}%  {s.playwright}")
    return 0


def _cmd_bug(args: argparse.Namespace) -> int:
    context = _load_context(args.context)
    result = FailureAnalyzer().analyze(context)
    bug = BugGenerationEngine().build(result, context)
    exporter = BugExporter()
    if args.out:
        written = exporter.export_all(bug, args.out)
        print(f"Wrote {len(written)} files to {args.out}:")
        for name in written:
            print(f"  - {name}")
        return 0
    fmt = args.format
    renderers = {
        "md": exporter.to_markdown,
        "html": exporter.to_html,
        "json": exporter.to_json,
        "txt": exporter.to_plaintext,
        "jira": exporter.to_jira_json,
        "azure": exporter.to_azure_json,
        "github": exporter.to_github_issue,
        "linear": exporter.to_linear_json,
    }
    print(renderers[fmt](bug))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiqa", description="AIQA SDK command-line interface.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="Classify a failure (category/owner/risk).")
    p_classify.add_argument("context", help="Path to a FailureContext JSON file.")
    p_classify.add_argument("--json", action="store_true", help="Emit JSON.")
    p_classify.set_defaults(func=_cmd_classify)

    p_explain = sub.add_parser(
        "explain-failure", help="Analyze a failure with AI confidence reasoning."
    )
    p_explain.add_argument("context", help="Path to a FailureContext JSON file.")
    p_explain.add_argument("--json", action="store_true", help="Emit JSON.")
    p_explain.set_defaults(func=_cmd_explain)

    p_heal = sub.add_parser("heal-locator", help="Suggest a healed locator from a DOM snapshot.")
    p_heal.add_argument("--old", required=True, help="The broken locator.")
    p_heal.add_argument("--dom", help="Path to an HTML/DOM snapshot file.")
    p_heal.add_argument("--text", help="Visible text of the target element.")
    p_heal.add_argument(
        "--attr",
        action="append",
        metavar="NAME=VALUE",
        help="Known attribute of the target element (repeatable).",
    )
    p_heal.add_argument("--json", action="store_true", help="Emit JSON.")
    p_heal.set_defaults(func=_cmd_heal)

    p_bug = sub.add_parser("generate-bug", help="Generate a professional bug report.")
    p_bug.add_argument("context", help="Path to a FailureContext JSON file.")
    p_bug.add_argument(
        "--format",
        choices=["md", "html", "json", "txt", "jira", "azure", "github", "linear"],
        default="md",
        help="Output format (ignored when --out is given).",
    )
    p_bug.add_argument("--out", help="Write all tracker formats to this directory.")
    p_bug.set_defaults(func=_cmd_bug)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        parser.error(f"file not found: {exc.filename}")
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
