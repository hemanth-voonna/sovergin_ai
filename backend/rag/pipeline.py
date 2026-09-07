"""End-to-end RAG pipeline.

Question -> embedding -> vector search -> context construction -> LLM
-> grounded answer with sources.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ai.embeddings import get_embedding_service
from ai.llm import get_llm, llm_configured
from app.config import settings
from .grounding import GROUNDING_SYSTEM_PROMPT, build_context, extractive_answer
from .vectorstore import Hit, get_vector_store


@dataclass
class RAGAnswer:
    question: str
    answer: str
    grounded: bool = True
    sources: list[dict] = field(default_factory=list)
    model: str = ""
    took_ms: int = 0
    mode: str = "llm"

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "grounded": self.grounded,
            "sources": self.sources,
            "model": self.model,
            "took_ms": self.took_ms,
            "mode": self.mode,
        }


class RAGPipeline:
    def __init__(self, vectorstore=None, embeddings=None, llm=None, top_k: int | None = None):
        self.vectorstore = vectorstore or get_vector_store()
        self.embeddings = embeddings or get_embedding_service()
        self.llm = llm or get_llm()
        self.top_k = top_k or settings.RAG_TOP_K

    def answer(self, question: str, document_ids: list[str] | None = None,
               top_k: int | None = None) -> RAGAnswer:
        start = time.monotonic()
        k = top_k or self.top_k

        query_embedding = self.embeddings.embed_one(question)
        hits = self.vectorstore.search(query_embedding, top_k=k, document_ids=document_ids)

        if not hits:
            from .grounding import NOT_FOUND_MESSAGE

            return RAGAnswer(
                question=question,
                answer=NOT_FOUND_MESSAGE,
                grounded=False,
                sources=[],
                model=self.llm.name,
                took_ms=int((time.monotonic() - start) * 1000),
                mode="extractive",
            )

        sources = [
            {
                "document_id": h.document_id,
                "filename": h.filename,
                "page": h.page,
                "chunk_index": h.chunk_index,
                "score": round(h.score, 4),
                "snippet": h.text[:400],
            }
            for h in hits
        ]

        if getattr(self.llm, "mode", "llm") == "mock":
            answer, grounded = extractive_answer(question, hits)
            mode = "extractive"
        else:
            context = build_context(hits)
            user_prompt = (
                f"<context>\n{context}\n</context>\n\n"
                f"Question: {question}\n\n"
                "Answer the question strictly from the context above, following all rules."
            )
            try:
                answer = self.llm.chat(
                    [
                        {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ]
                ).strip()
            except Exception as exc:
                answer = (
                    f"The LLM could not be reached ({exc}). The requested information "
                    "could not be verified from the provided documents."
                )
            grounded = "could not be found" not in answer.lower()
            mode = "llm"

        return RAGAnswer(
            question=question,
            answer=answer,
            grounded=grounded,
            sources=sources,
            model=self.llm.name,
            took_ms=int((time.monotonic() - start) * 1000),
            mode=mode,
        )


_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


def pipeline_uses_llm() -> bool:
    return llm_configured()