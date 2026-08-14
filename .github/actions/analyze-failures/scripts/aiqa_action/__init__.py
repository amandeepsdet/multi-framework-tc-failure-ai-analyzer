# AIQA GitHub Action — orchestration layer.
#
# This package is *orchestration only*. It discovers test artifacts, feeds them
# through the existing `aiqa` SDK (adapters -> FailureAnalyzer -> QualityPortal),
# and publishes the results to GitHub (Step Summary, PR comment, outputs,
# artifact). It contains NO failure-analysis logic of its own.

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
