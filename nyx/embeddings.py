"""Vector embeddings for semantic recall — dependency-free, with a live upgrade.

Memory recall improves from keyword overlap to **cosine similarity in a vector
space**. Two backends behind one ``Embedder`` protocol:

- ``HashingEmbedder`` (default): a deterministic, offline, pure-Python feature-
  hashing embedder over word + character n-grams. No numpy, no network — so it
  works on a mini-PC and in CI, and it captures sub-word overlap that plain
  Jaccard misses (typos, morphology, shared roots).
- ``ProviderEmbedder``: wraps a live Ollama Cloud embeddings model for true
  semantic similarity when a brain (and network) are available.

The store caches each lesson's vector, so recall is O(n) dot-products, not
re-embedding. If embedding fails, recall falls back to keyword overlap.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN = re.compile(r"[a-z0-9]+")

Vector = list[float]


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> Vector: ...


def cosine(a: Vector, b: Vector) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _features(text: str) -> list[str]:
    words = _TOKEN.findall(text.lower())
    feats: list[str] = list(words)
    # word bigrams (light phrase sense) + char trigrams (morphology/typos)
    feats += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    for w in words:
        pad = f"#{w}#"
        feats += [pad[i:i + 3] for i in range(len(pad) - 2)]
    return feats


class HashingEmbedder:
    """Deterministic feature-hashing embedder (offline, no dependencies)."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, text: str) -> Vector:
        vec = [0.0] * self.dim
        for feat in _features(text):
            h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "big")
            idx = h % self.dim
            sign = 1.0 if (h >> 63) & 1 else -1.0   # signed hashing reduces collisions
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class ProviderEmbedder:
    """Semantic embeddings from a live provider (used only when available)."""

    def __init__(self, provider, model: str, dim: int = 0):
        self.provider = provider
        self.model = model
        self.dim = dim

    def embed(self, text: str) -> Vector:
        vec = self.provider.embed(self.model, text)   # provider may raise; caller guards
        self.dim = self.dim or len(vec)
        return list(vec)


def default_embedder() -> Embedder:
    return HashingEmbedder()


def embedder_for(config, provider) -> Embedder:
    """Pick the best available embedder: real semantic embeddings from a live
    provider, else the deterministic offline hashing embedder."""
    if provider is not None and hasattr(provider, "embed") and not getattr(config, "mock_mode", True):
        return ProviderEmbedder(provider, getattr(config, "model_embed", "nomic-embed-text"))
    return HashingEmbedder()
