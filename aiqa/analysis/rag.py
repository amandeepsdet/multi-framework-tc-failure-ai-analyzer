"""Pluggable similarity / RAG backends over past failures.

The engine depends only on the :class:`~aiqa.core.interfaces.SimilarityIndex`
protocol. Two implementations ship by default:

* :class:`NullIndex` — disables RAG (no history, no dependencies).
* :class:`InMemoryIndex` — a pure-Python bag-of-words cosine index with
  optional JSON persistence, so similarity search works fully offline.

Swap in a vector-database-backed index by implementing the same protocol.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> Counter:
    return Counter(_TOKEN_RE.findall((text or "").lower()))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class NullIndex:
    """A no-op index; similarity search always returns nothing."""

    def add(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        return None

    def search(self, text: str, top_k: int) -> list[dict[str, Any]]:
        return []


class InMemoryIndex:
    """Pure-Python cosine-similarity index with optional JSON persistence."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._docs: list[dict[str, Any]] = []
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._load()

    def add(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        self._docs = [d for d in self._docs if d["id"] != doc_id]
        self._docs.append({"id": doc_id, "text": text, "metadata": dict(metadata)})
        if self._path:
            self._save()

    def search(self, text: str, top_k: int) -> list[dict[str, Any]]:
        query = _tokenize(text)
        scored = [
            {
                "score": _cosine(query, _tokenize(d["text"])),
                "text": d["text"],
                "metadata": d["metadata"],
            }
            for d in self._docs
        ]
        scored = [s for s in scored if s["score"] > 0]
        scored.sort(key=lambda s: s["score"], reverse=True)
        return scored[:top_k]

    # -- persistence -------------------------------------------------------- #
    def _load(self) -> None:
        try:
            self._docs = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            self._docs = []

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._docs, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
