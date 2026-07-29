"""Persistent, searchable failure history database (JSON files on disk).

Every failed execution is serialised to ``failure_history/<timestamp>_<test>.json``.
The store offers simple querying (by category, test, recency) used by the trend
analyzer, release-readiness scoring, and the QA assistant. It intentionally uses
flat JSON files — transparent, diff-able, and dependency-free.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .models import AnalysisResult, FailureRecord

logger = get_logger("ai.history_store")

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class HistoryStore:
    """Read/write access to the on-disk failure history."""

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg
        self.dir = cfg.history_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ write
    def save(self, record: FailureRecord, analysis: AnalysisResult | None = None) -> Path:
        """Persist a failure (and optional analysis) and return the file path."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_name = _SAFE.sub("_", record.test_name or "unknown").strip("_")[:80]
        record.record_id = record.record_id or f"{stamp}_{safe_name}"
        path = self.dir / f"{record.record_id}.json"
        payload: dict[str, Any] = {"record": record.to_dict()}
        if analysis is not None:
            payload["analysis"] = analysis.to_dict()
        try:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Saved failure record: %s", path.name)
        except OSError as exc:  # pragma: no cover - disk/OneDrive lock
            logger.warning("Could not save failure record: %s", exc)
        return path

    # ------------------------------------------------------------------- read
    def _iter_files(self):
        return sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def load_all(self) -> list[dict[str, Any]]:
        """Return every stored payload ({"record":..., "analysis":...})."""
        items: list[dict[str, Any]] = []
        for file in self._iter_files():
            try:
                items.append(json.loads(file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return items

    def records(self) -> list[FailureRecord]:
        return [FailureRecord.from_dict(item.get("record", {})) for item in self.load_all()]

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.load_all()[:limit]

    def latest(self) -> dict[str, Any] | None:
        items = self.recent(1)
        return items[0] if items else None

    def query(self, predicate: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        return [item for item in self.load_all() if predicate(item)]

    def by_category(self, category: str) -> list[dict[str, Any]]:
        needle = category.lower()
        return self.query(
            lambda item: (item.get("analysis", {}) or {}).get("category", "").lower() == needle
        )

    def by_test(self, test_name: str) -> list[dict[str, Any]]:
        needle = test_name.lower()
        return self.query(lambda item: needle in (item.get("record", {}).get("test_name", "").lower()))

    def count(self) -> int:
        return len(list(self._iter_files()))
