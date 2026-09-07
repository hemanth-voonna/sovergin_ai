"""RAG query API."""
from __future__ import annotations

from fastapi import APIRouter

from ..activity import log_event
from rag.pipeline import get_rag_pipeline
from ..schemas import RAGAnswerOut, RAGQueryIn
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/rag", tags=["rag"], dependencies=[deps.auth])


@router.post("/query", response_model=RAGAnswerOut)
def query_rag(payload: RAGQueryIn):
    answer = get_rag_pipeline().answer(
        question=payload.question,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
    )
    log_event(
        "rag_query", f"RAG query: {payload.question[:120]}",
        details={
            "question": payload.question[:500],
            "grounded": answer.grounded,
            "sources": len(answer.sources),
            "mode": answer.mode,
        },
    )
    return RAGAnswerOut(**answer.to_dict())