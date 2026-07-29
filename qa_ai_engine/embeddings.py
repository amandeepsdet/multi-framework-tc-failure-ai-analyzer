"""Text embedding abstraction for semantic failure search (RAG).

The default :class:`HashEmbedder` is pure Python with no dependencies and no
network — it hashes token n-grams into a fixed-dimension vector. It is not as
semantically rich as a neural embedding, but it is deterministic, free, and
good enough to cluster similar stack traces / error messages offline. Swap in
:class:`OpenAIEmbedder` (or your own) via configuration for higher quality.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

from ._logging import get_logger

from .ai_config import AIConfig, ai_config

logger = get_logger("ai.embeddings")

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class BaseEmbedder(ABC):
    """Abstract text embedder."""

    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a dense vector for ``text``."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class HashEmbedder(BaseEmbedder):
    """Deterministic hashing embedder (bag of hashed token unigrams+bigrams)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = max(16, dim)

    def _tokens(self, text: str) -> list[str]:
        words = _TOKEN_RE.findall((text or "").lower())
        bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
        return words + bigrams

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in self._tokens(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embeddings (lazily imported; requires an API key)."""

    def __init__(self, cfg: AIConfig) -> None:
        self.cfg = cfg
        self.dim = cfg.embedding_dim

    def embed(self, text: str) -> list[float]:
        import os

        import openai

        client = openai.OpenAI(api_key=self.cfg.api_key or os.getenv("OPENAI_API_KEY", ""))
        resp = client.embeddings.create(model=self.cfg.embedding_model, input=text or " ")
        return list(resp.data[0].embedding)


def get_embedder(cfg: AIConfig = ai_config) -> BaseEmbedder:
    """Factory: build the configured embedder, defaulting to hashing."""
    provider = (cfg.embedding_provider or "hash").lower()
    if provider in {"openai", "azure"}:
        try:
            return OpenAIEmbedder(cfg)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Falling back to HashEmbedder (%s)", exc)
    return HashEmbedder(cfg.embedding_dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0 when degenerate)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
