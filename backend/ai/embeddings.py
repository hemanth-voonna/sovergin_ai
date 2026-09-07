"""Embedding providers — always computed locally, never an external API.

Providers:
  * chroma — ONNX `all-MiniLM-L6-v2` bundled with Chroma (384 dims, local).
    The model file is read from Chroma's local cache ONLY. If the model has
    not been provisioned on this machine, the provider refuses to download it
    at runtime (sovereign/offline guarantee) and auto falls back to hash.
  * hash   — deterministic hashing embeddings (zero-download fallback).

Provision the ONNX model once (while online) with:
    python backend/scripts/embed_setup.py
or rely on the Docker image, which bakes it at build time. Until then the app
still works fully offline via the hash provider.

`EMBEDDINGS_PROVIDER=auto` uses chroma only when the model is cached locally,
otherwise it transparently uses the hash provider — no network either way.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

HASH_DIM = 384


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class HashEmbeddingProvider:
    """Deterministic, dependency-free embeddings.

    Each token hashes to a signed dimension; vectors are L2-normalised.
    Good enough for retrieval demos and for running fully offline.
    """

    name = "hash"

    def __init__(self, dim: int = HASH_DIM):
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _tokens(text):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % self.dim
                vec[idx] += 1.0 if h % 2 == 0 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


# Model handled by Chroma's bundled DefaultEmbeddingFunction. Keep in sync
# with chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2.
_ONNX_MODEL = "all-MiniLM-L6-v2"


def _onnx_model_cached() -> bool:
    """True when the ONNX model is already present in Chroma's local cache.

    If the file is absent we must NOT let Chroma download it at runtime.
    """
    candidate = (
        Path.home()
        / ".cache" / "chroma" / "onnx_models" / _ONNX_MODEL / "onnx" / "model.onnx"
    )
    return candidate.is_file()


class ChromaEmbeddingProvider:
    """Wraps Chroma's bundled ONNX all-MiniLM-L6-v2 (local, no key, no download)."""

    name = "chroma-onnx"

    def __init__(self) -> None:
        if not _onnx_model_cached():
            raise RuntimeError(
                "Chroma ONNX model not found in the local cache. The app refuses to "
                "download models at runtime (sovereign/offline mode). Provision it once "
                "while online with `python backend/scripts/embed_setup.py`, or set "
                "EMBEDDINGS_PROVIDER=hash for a fully offline zero-model mode."
            )
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._fn = DefaultEmbeddingFunction()
        self._dim = 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        result = self._fn(texts)
        if isinstance(result, np.ndarray):
            return result.tolist()
        return [list(map(float, r)) for r in result]

    @property
    def dim(self) -> int:
        return self._dim


class EmbeddingService:
    """Facade that hides provider selection / fallback."""

    def __init__(self, provider: str = "auto"):
        self._requested = provider
        self._active: HashEmbeddingProvider | ChromaEmbeddingProvider | None = None
        self._fallback_used = False

    # -- lifecycle -----------------------------------------------------
    def _ensure(self) -> HashEmbeddingProvider | ChromaEmbeddingProvider:
        if self._active is not None:
            return self._active
        if self._requested == "hash":
            self._active = HashEmbeddingProvider()
            return self._active
        if self._requested in ("chroma", "auto"):
            try:
                self._active = ChromaEmbeddingProvider()
                # force a tiny warm-up so failures surface now, not mid-query
                self._active.embed_texts(["warm-up"])
                logger.info("Embeddings: using Chroma ONNX provider (384d)")
                return self._active
            except Exception as exc:
                logger.warning("Chroma ONNX embeddings unavailable (%s); using hash fallback.", exc)
                self._fallback_used = True
        self._active = HashEmbeddingProvider()
        return self._active

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._ensure().embed_texts(texts)

    def embed_one(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    # -- introspection for settings UI --------------------------------
    @property
    def provider_name(self) -> str:
        return self._ensure().name + (" (fallback)" if self._fallback_used else "")

    @property
    def dim(self) -> int:
        return self._ensure().dim

    @property
    def fallback_used(self) -> bool:
        return self._fallback_used


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(settings.EMBEDDINGS_PROVIDER)