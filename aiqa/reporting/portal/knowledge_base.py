"""AI Knowledge Base — a persistent memory of failure signatures.

Every execution feeds its failures here. For each unique failure signature the
knowledge base tracks how often it has been seen, when, its owner, category,
best-known fix and average confidence. This powers "failure memory" (has this
been seen before?) and cross-run insight generation.

Storage is a single JSON document so it works fully offline with no database.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ExecutionRun, RunFailure, failure_signature, utc_now_iso


@dataclass
class KnowledgeEntry:
    signature: str = ""
    test_id: str = ""
    test_name: str = ""
    category: str = ""
    root_cause: str = ""
    owner: str = ""
    suggested_fix: str = ""
    framework: str = ""
    occurrences: int = 0
    confidence_sum: int = 0
    first_seen: str = ""
    last_seen: str = ""
    last_run_id: str = ""
    fixes: dict[str, int] = field(default_factory=dict)

    @property
    def avg_confidence(self) -> float:
        return round(self.confidence_sum / self.occurrences, 1) if self.occurrences else 0.0

    @property
    def most_successful_fix(self) -> str:
        if self.fixes:
            return max(self.fixes.items(), key=lambda kv: kv[1])[0]
        return self.suggested_fix

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "test_id": self.test_id,
            "test_name": self.test_name,
            "category": self.category,
            "root_cause": self.root_cause,
            "owner": self.owner,
            "suggested_fix": self.suggested_fix,
            "framework": self.framework,
            "occurrences": self.occurrences,
            "avg_confidence": self.avg_confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "last_run_id": self.last_run_id,
            "fixes": dict(self.fixes),
            "confidence_sum": self.confidence_sum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeEntry:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


@dataclass
class FailureMemory:
    """What the knowledge base remembers about a specific failure."""

    seen_before: bool = False
    occurrences: int = 0
    last_occurrence: str = ""
    most_successful_fix: str = ""
    owner: str = ""
    avg_confidence: float = 0.0
    similarity: int = 0


class KnowledgeBase:
    """Load, query and update the persistent failure-signature memory."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.entries: dict[str, KnowledgeEntry] = {}
        self.load()

    # -- persistence -------------------------------------------------------- #
    def load(self) -> None:
        self.entries = {}
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for sig, raw in (data.get("signatures") or {}).items():
            self.entries[sig] = KnowledgeEntry.from_dict(raw)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": utc_now_iso(),
            "signatures": {sig: e.to_dict() for sig, e in self.entries.items()},
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- queries ------------------------------------------------------------ #
    def recall(self, failure: RunFailure) -> FailureMemory:
        """Return the knowledge base's memory of a failure (before recording it)."""
        entry = self.entries.get(failure.signature)
        if entry is None:
            return FailureMemory(seen_before=False, similarity=0)
        return FailureMemory(
            seen_before=True,
            occurrences=entry.occurrences,
            last_occurrence=entry.last_seen,
            most_successful_fix=entry.most_successful_fix,
            owner=entry.owner,
            avg_confidence=entry.avg_confidence,
            similarity=100,
        )

    # -- updates ------------------------------------------------------------ #
    def record_run(self, run: ExecutionRun) -> None:
        """Fold every failure of a run into the knowledge base and persist."""
        now = run.finished or run.started or utc_now_iso()
        for f in run.failures:
            sig = f.signature or failure_signature(f.test_id, f.category)
            entry = self.entries.get(sig)
            if entry is None:
                entry = KnowledgeEntry(
                    signature=sig,
                    test_id=f.test_id,
                    test_name=f.test_name,
                    category=f.category,
                    root_cause=f.root_cause,
                    owner=f.owner,
                    suggested_fix=f.suggested_fix,
                    framework=f.framework,
                    first_seen=now,
                )
                self.entries[sig] = entry
            entry.occurrences += 1
            entry.confidence_sum += int(f.confidence)
            entry.last_seen = now
            entry.last_run_id = run.run_id
            entry.owner = f.owner or entry.owner
            entry.category = f.category or entry.category
            entry.root_cause = f.root_cause or entry.root_cause
            if f.suggested_fix:
                entry.suggested_fix = f.suggested_fix
                entry.fixes[f.suggested_fix] = entry.fixes.get(f.suggested_fix, 0) + 1
        self.save()

    def top_recurring(self, limit: int = 10) -> list[KnowledgeEntry]:
        return sorted(self.entries.values(), key=lambda e: -e.occurrences)[:limit]
