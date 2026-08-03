"""Execution history management.

Owns the ``reports/`` directory: the append-only ``history.json`` index, the
``latest.json`` pointer, and discovery of per-run folders. It never renders
HTML — it only stores and serves :class:`ExecutionRun` records.

``history.json`` holds *lightweight* run summaries (headline metrics plus
compact failure signatures), so the index scales to thousands of runs. The full
per-run detail lives in each ``run_*/execution_summary.json``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .models import ExecutionRun


class ExecutionHistoryManager:
    """Reads and writes the run history under a reports root directory."""

    HISTORY_FILE = "history.json"
    LATEST_FILE = "latest.json"
    RUN_PREFIX = "run_"

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # -- paths -------------------------------------------------------------- #
    @property
    def history_path(self) -> Path:
        return self.root / self.HISTORY_FILE

    @property
    def latest_path(self) -> Path:
        return self.root / self.LATEST_FILE

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    # -- loading ------------------------------------------------------------ #
    def load(self) -> list[ExecutionRun]:
        """Load run summaries from history.json (oldest first)."""
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        runs = [ExecutionRun.from_dict(r) for r in (data.get("runs") or [])]
        runs.sort(key=lambda r: r.run_id)
        return runs

    def latest(self) -> ExecutionRun | None:
        runs = self.load()
        return runs[-1] if runs else None

    # -- writing ------------------------------------------------------------ #
    def add_run(self, run: ExecutionRun) -> list[ExecutionRun]:
        """Append (or replace) a run in history.json and refresh latest.json."""
        self.root.mkdir(parents=True, exist_ok=True)
        runs = [r for r in self.load() if r.run_id != run.run_id]
        runs.append(run)
        runs.sort(key=lambda r: r.run_id)
        self._write_history(runs)
        self._write_latest(run)
        return runs

    def delete_run(self, run_id: str) -> list[ExecutionRun]:
        """Remove a run from history and delete its folder."""
        runs = [r for r in self.load() if r.run_id != run_id]
        self._write_history(runs)
        folder = self.run_dir(run_id)
        if folder.exists() and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
        if runs:
            self._write_latest(runs[-1])
        elif self.latest_path.exists():
            self.latest_path.unlink()
        return runs

    def _write_history(self, runs: list[ExecutionRun]) -> None:
        payload = {"runs": [r.to_summary_dict() for r in runs]}
        self.history_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write_latest(self, run: ExecutionRun) -> None:
        self.latest_path.write_text(
            json.dumps(run.to_summary_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
