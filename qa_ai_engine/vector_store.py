"""Vector store abstraction backing semantic RAG search.

The default :class:`JSONVectorStore` persists vectors to a single JSON file and
performs brute-force cosine search in pure Python — zero external services, safe
for a fresh checkout. For larger corpora, set ``AI_VECTOR_BACKEND=chroma`` to
use ChromaDB (lazily imported). Both satisfy the same :class:`BaseVectorStore`
interface, so callers never change.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._logging import get_logger
from .ai_config import AIConfig, ai_config
from .embeddings import BaseEmbedder, cosine_similarity, get_embedder

logger = get_logger("ai.vector_store")


@dataclass
class VectorHit:
    """A single search result."""

    id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": round(self.score, 4),
            "text": self.text,
            "metadata": self.metadata,
        }


class BaseVectorStore(ABC):
    """Abstract vector index."""

    @abstractmethod
    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Insert or replace a document."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[VectorHit]:
        """Return the ``top_k`` most similar documents to ``query``."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of indexed documents."""


class JSONVectorStore(BaseVectorStore):
    """File-backed, dependency-free vector store with cosine search."""

    def __init__(self, path: Path, embedder: BaseEmbedder) -> None:
        self.path = path
        self.embedder = embedder
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._docs: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read vector store (%s); starting fresh", exc)
        return {}

    def _persist(self) -> None:
        try:
            self.path.write_text(json.dumps(self._docs, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - disk/OneDrive lock
            logger.warning("Could not persist vector store: %s", exc)

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._docs[doc_id] = {
                "text": text,
                "metadata": metadata or {},
                "embedding": self.embedder.embed(text),
            }
            self._persist()

    def search(self, query: str, top_k: int = 5) -> list[VectorHit]:
        if not self._docs:
            return []
        query_vec = self.embedder.embed(query)
        scored = [
            VectorHit(
                id=doc_id,
                score=cosine_similarity(query_vec, doc.get("embedding", [])),
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
            )
            for doc_id, doc in self._docs.items()
        ]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return [hit for hit in scored[:top_k] if hit.score > 0]

    def count(self) -> int:
        return len(self._docs)


class ChromaVectorStore(BaseVectorStore):  # pragma: no cover - optional dependency
    """ChromaDB-backed store (lazily imported)."""

    def __init__(self, path: Path, embedder: BaseEmbedder) -> None:
        import chromadb

        self.embedder = embedder
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection("failures")

    def add(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            embeddings=[self.embedder.embed(text)],
            metadatas=[metadata or {}],
        )

    def search(self, query: str, top_k: int = 5) -> list[VectorHit]:
        result = self._collection.query(
            query_embeddings=[self.embedder.embed(query)], n_results=top_k
        )
        hits: list[VectorHit] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, doc_id in enumerate(ids):
            hits.append(
                VectorHit(
                    id=doc_id,
                    score=1.0 - float(dists[i]) if i < len(dists) else 0.0,
                    text=docs[i] if i < len(docs) else "",
                    metadata=metas[i] if i < len(metas) else {},
                )
            )
        return hits

    def count(self) -> int:
        return self._collection.count()


def get_vector_store(
    cfg: AIConfig = ai_config, embedder: BaseEmbedder | None = None
) -> BaseVectorStore:
    """Factory: build the configured vector store, defaulting to JSON."""
    embedder = embedder or get_embedder(cfg)
    backend = (cfg.vector_backend or "json").lower()
    cfg.vector_dir.mkdir(parents=True, exist_ok=True)
    if backend in {"chroma", "chromadb"}:
        try:
            return ChromaVectorStore(cfg.vector_dir, embedder)
        except Exception as exc:  # pragma: no cover
            logger.warning("ChromaDB unavailable (%s); using JSON store", exc)
    return JSONVectorStore(cfg.vector_dir / "vector_store.json", embedder)
