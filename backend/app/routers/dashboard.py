"""Dashboard statistics API."""
from __future__ import annotations

import os
import time

import psutil

from fastapi import APIRouter

from ..activity import activity_series, recent_activity
from ai.embeddings import get_embedding_service
from ai.llm import get_llm
from ..config import settings as real_settings
from ..database import SessionLocal
from ..models import Activity
from ocr.engine import ocr_available, ocr_engine_name
from rag.vectorstore import get_vector_store
from ..schemas import DashboardOut
from ..services import get_document_stats
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[deps.auth])

_START = time.time()


def system_health() -> dict:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(real_settings.DATA_DIR)
    vector_store = get_vector_store()
    services = {
        "database": "ok",
        "vectorstore": "ok" if vector_store.name else "unavailable",
        "embeddings": get_embedding_service().provider_name,
        "llm": get_llm().name,
        "ocr": (f"ok ({ocr_engine_name()})" if ocr_available()
                else "unavailable (install tesseract or pip install rapidocr-onnxruntime)"),
    }
    return {
        "status": "ok",
        "version": real_settings.VERSION,
        "uptime_s": round(time.time() - _START, 1),
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "memory": {"used_gb": round(mem.used / 1e9, 2), "total_gb": round(mem.total / 1e9, 2),
                   "percent": mem.percent},
        "disk": {"used_gb": round(disk.used / 1e9, 2), "total_gb": round(disk.total / 1e9, 2),
                 "percent": disk.percent},
        "services": services,
    }


def _count_actions() -> dict[str, int]:
    db = SessionLocal()
    try:
        from sqlalchemy import func, select

        rows = db.execute(
            select(Activity.action, func.count(Activity.id)).group_by(Activity.action)
        ).all()
        return {action: count for action, count in rows}
    finally:
        db.close()


@router.get("", response_model=DashboardOut)
def dashboard():
    counts = _count_actions()
    return DashboardOut(
        documents=get_document_stats(),
        rag_queries=counts.get("rag_query", 0),
        agent_runs=counts.get("agent_run", 0),
        sandbox_runs=counts.get("sandbox", 0),
        vectors_indexed=get_vector_store().count(),
        health=system_health(),
        recent_activity=recent_activity(12),
        activity_series=activity_series(7),
    )