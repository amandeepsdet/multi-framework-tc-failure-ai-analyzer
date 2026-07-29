"""Optional LLM-vision analysis of failure screenshots.

When ``AI_VISION_ENABLED`` is on and the configured provider supports vision,
the collected screenshot is inspected to answer concrete, evidence-based
questions (missing widget, spinner, blank dashboard, broken layout, auth page).
When vision is unavailable the analyzer returns a clearly-marked "skipped"
result so callers can degrade gracefully.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .llm_client import BaseLLMClient, extract_json, get_llm_client
from .prompt_builder import PromptBuilder

logger = get_logger("ai.visual_analyzer")


@dataclass
class VisualFindings:
    widget_missing: bool = False
    spinner_visible: bool = False
    dashboard_blank: bool = False
    layout_broken: bool = False
    auth_page_shown: bool = False
    summary: str = ""
    available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VisualAnalyzer:
    """Runs vision questions against a screenshot when supported."""

    def __init__(
        self,
        cfg: AIConfig = ai_config,
        llm: BaseLLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.cfg = cfg
        self.llm = llm or get_llm_client(cfg)
        self.prompts = prompt_builder or PromptBuilder(cfg)

    def available(self) -> bool:
        return bool(
            self.cfg.vision_enabled
            and self.llm.is_available()
            and self.llm.supports_vision()
        )

    def analyze(self, screenshot_path: str | None) -> VisualFindings:
        if not self.available():
            return VisualFindings(available=False, summary="Vision analysis disabled or unsupported.")
        if not screenshot_path or not os.path.exists(screenshot_path):
            return VisualFindings(available=False, summary="No screenshot available for vision analysis.")
        try:
            prompt = self.prompts.load_template("visual_analysis")
            raw = self.llm.complete_vision(prompt, screenshot_path)
            data = extract_json(raw)
            return VisualFindings(
                widget_missing=bool(data.get("widget_missing")),
                spinner_visible=bool(data.get("spinner_visible")),
                dashboard_blank=bool(data.get("dashboard_blank")),
                layout_broken=bool(data.get("layout_broken")),
                auth_page_shown=bool(data.get("auth_page_shown")),
                summary=data.get("summary", ""),
                available=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vision analysis failed: %s", exc)
            return VisualFindings(available=False, summary=f"Vision analysis error: {exc}")
