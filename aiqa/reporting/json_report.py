"""JSON reporter."""

from __future__ import annotations

import json

from ..core.interfaces import Reporter
from ..core.models import AnalysisResult, FailureContext
from .base import register_reporter


@register_reporter
class JSONReporter(Reporter):
    format = "json"

    def render(self, result: AnalysisResult, context: FailureContext | None = None) -> str:
        payload = {"analysis": result.to_dict()}
        if context is not None:
            payload["context"] = {
                "test_name": context.test_name,
                "framework": context.metadata.framework,
                "environment": context.execution.environment,
            }
        return json.dumps(payload, indent=2, ensure_ascii=False)
