"""AIQA reporting — renders an AnalysisResult into output formats.

Depends only on the core domain. Importing this package registers the built-in
reporters (markdown, json, html, console) in the reporter registry.
"""

from __future__ import annotations

from .base import available_formats, get_reporter, register_reporter
from .bug_report import BugReportBuilder
from .console import ConsoleReporter
from .html import HTMLReporter
from .json_report import JSONReporter
from .markdown import MarkdownReporter

__all__ = [
    "available_formats",
    "get_reporter",
    "register_reporter",
    "BugReportBuilder",
    "ConsoleReporter",
    "HTMLReporter",
    "JSONReporter",
    "MarkdownReporter",
]
