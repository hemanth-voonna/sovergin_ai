"""Embedding provider tests."""
from __future__ import annotations

import pytest

from ai.embeddings import EmbeddingService, HashEmbeddingProvider


def test_hash_embeddings_deterministic():
    provider = HashEmbeddingProvider()
    a = provider.embed_texts(["the registered owner is Sunita Patil"])
    b = provider.embed_texts(["the registered owner is Sunita Patil"])
    assert a == b
    assert len(a[0]) == provider.dim


def test_hash_embeddings_similar_texts_close():
    provider = HashEmbeddingProvider()
    [x] = provider.embed_texts(["village kamalpur district nashik"])
    [y] = provider.embed_texts(["kamalpur village nashik district"])
    [z] = provider.embed_texts(["completely unrelated topic about weather"])
    import math

    def cos(a, b):
        dot = sum(i * j for i, j in zip(a, b))
        return dot / (math.sqrt(sum(i * i for i in a)) * math.sqrt(sum(j * j for j in b)))

    assert cos(x, y) > cos(x, z)


def test_service_hash_mode():
    svc = EmbeddingService(provider="hash")
    embs = svc.embed_texts(["hello world", "second text"])
    assert len(embs) == 2
    assert svc.provider_name == "hash"
    assert svc.dim == 384


def test_service_falls_back_to_hash_on_chroma_failure(monkeypatch):
    def boom(self, texts):
        raise RuntimeError("no network")

    monkeypatch.setattr("ai.embeddings.ChromaEmbeddingProvider.embed_texts", boom)
    svc = EmbeddingService(provider="auto")
    embs = svc.embed_texts(["fallback works"])
    assert len(embs[0]) == 384
    assert svc.fallback_used is True
    assert svc.provider_name == "hash (fallback)"


def test_embed_one():
    svc = EmbeddingService(provider="hash")
    vec = svc.embed_one("single string")
    assert len(vec) == 384