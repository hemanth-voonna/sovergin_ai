"""Vector store tests."""
from __future__ import annotations

import pytest

from ai.embeddings import EmbeddingService
from rag.chunker import Chunk
from rag.vectorstore import InMemoryVectorStore

EMB = EmbeddingService(provider="hash")


def _chunks() -> list[Chunk]:
    return [
        Chunk(text="The registered owner is Sunita Vishnu Patil of Kamalpur village.", page=1, chunk_index=0),
        Chunk(text="The survey number is 124/3 and the land area is 2.35 hectares.", page=1, chunk_index=1),
        Chunk(text="Document date is 15/08/2023 at the Nashik registrar office.", page=2, chunk_index=2),
    ]


def test_add_search_roundtrip():
    store = InMemoryVectorStore()
    chunks = _chunks()
    n = store.add_chunks("doc-1", "record.txt", chunks, EMB.embed_texts([c.text for c in chunks]))
    assert n == 3
    assert store.count() == 3

    hits = store.search(EMB.embed_one("who is the registered owner sunita patil"), top_k=2)
    assert len(hits) == 2
    assert hits[0].document_id == "doc-1"
    assert hits[0].filename == "record.txt"
    assert "Sunita" in hits[0].text


def test_search_document_filter():
    store = InMemoryVectorStore()
    chunks = _chunks()
    emb = EMB.embed_texts([c.text for c in chunks])
    store.add_chunks("doc-1", "a.txt", chunks, emb)
    store.add_chunks("doc-2", "b.txt", chunks, emb)

    hits = store.search(EMB.embed_one("survey number"), top_k=5, document_ids=["doc-2"])
    assert all(h.document_id == "doc-2" for h in hits)


def test_delete_document():
    store = InMemoryVectorStore()
    chunks = _chunks()
    emb = EMB.embed_texts([c.text for c in chunks])
    store.add_chunks("doc-1", "a.txt", chunks, emb)
    store.add_chunks("doc-2", "b.txt", chunks, emb)
    store.delete_document("doc-1")
    assert store.count() == 3
    hits = store.search(EMB.embed_one("anything"), top_k=10)
    assert all(h.document_id == "doc-2" for h in hits)


def test_search_empty_store():
    store = InMemoryVectorStore()
    assert store.search(EMB.embed_one("nothing here")) == []


@pytest.mark.integration
def test_chroma_store_roundtrip(tmp_path):
    from rag.vectorstore import ChromaVectorStore

    store = ChromaVectorStore(path=str(tmp_path / "chroma"))
    chunks = _chunks()
    emb = EMB.embed_texts([c.text for c in chunks])
    store.add_chunks("doc-1", "record.txt", chunks, emb)
    assert store.count() == 3

    hits = store.search(EMB.embed_one("registered owner sunita"), top_k=2)
    assert hits and hits[0].document_id == "doc-1"

    store.delete_document("doc-1")
    assert store.count() == 0