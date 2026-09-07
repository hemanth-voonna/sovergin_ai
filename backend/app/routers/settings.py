"""Runtime configuration overview (read-only, no secrets)."""
from __future__ import annotations

from fastapi import APIRouter

from ai.embeddings import get_embedding_service
from ai.llm import llm_configured
from ..config import settings
from rag.vectorstore import get_vector_store
from ..schemas import SettingsOut
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[deps.auth])


@router.get("", response_model=SettingsOut)
def get_settings_info():
    return SettingsOut(
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        llm_configured=llm_configured(),
        embedding_provider=get_embedding_service().provider_name,
        embedding_model=settings.EMBEDDING_MODEL,
        vector_db=get_vector_store().name,
        ocr_lang=settings.OCR_LANG,
        max_upload_mb=settings.MAX_UPLOAD_MB,
        auth_enabled=settings.auth_enabled,
        sandbox_executor=settings.SANDBOX_EXECUTOR,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        top_k=settings.RAG_TOP_K,
    )