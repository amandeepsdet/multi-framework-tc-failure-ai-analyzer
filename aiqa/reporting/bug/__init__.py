"""Intelligent bug generation — enriched reports and multi-tracker export.

Public surface::

    from aiqa.reporting.bug import BugGenerationEngine, BugExporter

    bug = BugGenerationEngine().build(result, context)
    print(BugExporter().to_markdown(bug))
    BugExporter().export_all(bug, "out/")

Framework-agnostic and offline; depends only on the core domain models.
"""

from __future__ import annotations

from .engine import BugGenerationEngine
from .exporters import BugExporter
from .titles import bug_title

__all__ = ["BugGenerationEngine", "BugExporter", "bug_title"]
