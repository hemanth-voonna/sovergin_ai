"""RAG pipeline tests (in-memory store + hash embeddings + mock LLM)."""
from __future__ import annotations

from pathlib import Path

from ai.embeddings import EmbeddingService
from ai.llm import MockGroundedLLM
from rag.chunker import chunk_pages
from rag.pipeline import RAGPipeline
from rag.vectorstore import InMemoryVectorStore

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

NOT_FOUND = "could not be found in the provided documents"


def _pipeline() -> RAGPipeline:
    text = (SAMPLES / "land_record.txt").read_text(encoding="utf-8")
    chunks = chunk_pages([(1, text)])
    store = InMemoryVectorStore()
    emb = EmbeddingService(provider="hash")
    store.add_chunks("doc-1", "land_record.txt", chunks, emb.embed_texts([c.text for c in chunks]))
    return RAGPipeline(vectorstore=store, embeddings=emb, llm=MockGroundedLLM(), top_k=5)


def test_grounded_answer_with_sources():
    pipe = _pipeline()
    ans = pipe.answer("Who is the registered owner?")
    assert ans.grounded is True
    assert "Sunita Vishnu Patil" in ans.answer
    assert len(ans.sources) >= 1
    src = ans.sources[0]
    assert src["document_id"] == "doc-1"
    assert src["filename"] == "land_record.txt"
    assert src["page"] is not None
    assert src["snippet"]


def test_answers_sample_questions():
    pipe = _pipeline()
    expected = {
        "What is the survey number?": "124/3",
        "What is the land area?": "2.35 hectares",
        "What is the document date?": "15/08/2023",
        "Which village does the land belong to?": "Kamalpur",
    }
    for q, fragment in expected.items():
        ans = pipe.answer(q)
        assert ans.grounded, q
        assert fragment in ans.answer, f"{q} -> {ans.answer}"


def test_out_of_corpus_question_not_hallucinated():
    pipe = _pipeline()
    ans = pipe.answer("What is the capital of France?")
    assert ans.grounded is False
    assert NOT_FOUND in ans.answer.lower()


def test_no_hits_returns_not_found():
    pipe = RAGPipeline(vectorstore=InMemoryVectorStore(), embeddings=EmbeddingService(provider="hash"),
                       llm=MockGroundedLLM())
    ans = pipe.answer("anything at all")
    assert ans.grounded is False
    assert NOT_FOUND in ans.answer.lower()
    assert ans.sources == []


def test_document_filter_limits_sources():
    pipe = _pipeline()
    ans = pipe.answer("What is the survey number?", document_ids=["does-not-exist"])
    assert ans.grounded is False or all(
        s["document_id"] == "does-not-exist" for s in ans.sources
    )