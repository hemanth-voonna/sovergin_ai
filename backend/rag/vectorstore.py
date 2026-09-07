"""Vector store layer.

Kept behind a small interface so the underlying engine (Chroma today,
Qdrant/Postgres pgvector tomorrow) can be swapped without touching the
RAG pipeline or the API. Embeddings are ALWAYS produced by the shared
EmbeddingService so provider fallback stays consistent end to end.

Privacy: the engine runs as a local, embedded, persistent store and Chroma's
product telemetry is disabled (env var set in app/config.py before any import,
plus Settings(anonymized_telemetry=False) below).
"""
from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from ai.embeddings import get_embedding_service
from app.config import settings
from .chunker import Chunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "sovereign_documents"


@dataclass
class Hit:
    document_id: str
    filename: str
    text: str
    page: int | None = None
    chunk_index: int | None = None
    score: float = 0.0  # similarity, higher is better (0..1)

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "text": self.text,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "score": round(self.score, 4),
        }


class VectorStore(ABC):
    name: str = "abstract"

    @abstractmethod
    def add_chunks(self, document_id: str, filename: str, chunks: list[Chunk],
                   embeddings: list[list[float]] | None = None) -> int: ...

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int = 5,
               document_ids: list[str] | None = None) -> list[Hit]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...


class ChromaVectorStore(VectorStore):
    """Persistent Chroma backend (local, open source)."""

    name = "chroma"

    def __init__(self, path: str | None = None):
        import chromadb

        self._path = path or settings.VECTOR_DB_PATH
        # Telemetry must stay off: this is an embedded local store and the
        # backend guarantees it never phones home.
        self._client = chromadb.PersistentClient(
            path=self._path,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, document_id: str, filename: str, chunks: list[Chunk],
                   embeddings: list[list[float]] | None = None) -> int:
        if not chunks:
            return 0
        if embeddings is None:
            embeddings = get_embedding_service().embed_texts([c.text for c in chunks])
        ids = [f"{document_id}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "page": c.page if c.page is not None else -1,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]
        self._collection.upsert(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )
        return len(chunks)

    def search(self, query_embedding: list[float], top_k: int = 5,
               document_ids: list[str] | None = None) -> list[Hit]:
        if self._collection.count() == 0:
            return []
        where = None
        if document_ids:
            where = {"document_id": {"$in": document_ids}}
        try:
            res = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("Chroma query failed (%s); returning no hits.", exc)
            return []

        hits: list[Hit] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for _id, text, meta, dist in zip(ids, docs, metas, dists):
            if text is None:
                continue
            meta = meta or {}
            raw_page = meta.get("page")
            page = int(raw_page) if raw_page is not None and int(raw_page) >= 0 else None
            hits.append(
                Hit(
                    document_id=str(meta.get("document_id", "")),
                    filename=str(meta.get("filename", "")),
                    text=str(text),
                    page=page,
                    chunk_index=int(meta.get("chunk_index", -1)),
                    score=float(1.0 - dist) if dist is not None else 0.0,
                )
            )
        return hits

    def delete_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception as exc:
            logger.warning("Chroma delete failed (%s)", exc)

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0


class InMemoryVectorStore(VectorStore):
    """Pure-Python store used by tests / zero-dependency fallback.

    Keeps embeddings so cosine search behaves exactly like the real engine.
    """

    name = "in-memory"

    def __init__(self) -> None:
        self._items: list[dict] = []

    def add_chunks(self, document_id: str, filename: str, chunks: list[Chunk],
                   embeddings: list[list[float]] | None = None) -> int:
        if embeddings is None:
            embeddings = get_embedding_service().embed_texts([c.text for c in chunks])
        for c, emb in zip(chunks, embeddings):
            self._items.append(
                {
                    "chunk_id": f"{document_id}:{c.chunk_index}",
                    "document_id": document_id,
                    "filename": filename,
                    "text": c.text,
                    "page": c.page,
                    "chunk_index": c.chunk_index,
                    "embedding": emb,
                }
            )
        return len(chunks)

    def search(self, query_embedding: list[float], top_k: int = 5,
               document_ids: list[str] | None = None) -> list[Hit]:
        matches = self._items
        if document_ids:
            id_set = set(document_ids)
            matches = [m for m in matches if m["document_id"] in id_set]
        scored = [(m, _cosine(query_embedding, m["embedding"])) for m in matches]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            Hit(
                document_id=m["document_id"],
                filename=m["filename"],
                text=m["text"],
                page=m["page"],
                chunk_index=m["chunk_index"],
                score=score,
            )
            for m, score in scored[:top_k]
        ]

    def delete_document(self, document_id: str) -> None:
        self._items = [m for m in self._items if m["document_id"] != document_id]

    def count(self) -> int:
        return len(self._items)


def _cosine(a: list[float], b: list[float]) -> float:
    if not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


@lru_cache
def get_vector_store() -> VectorStore:
    store: VectorStore = ChromaVectorStore()
    logger.info("Vector store ready: %s at %s", store.name, settings.VECTOR_DB_PATH)
    return store