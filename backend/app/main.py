"""SovereignAI Workbench — FastAPI application entrypoint."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import agents, dashboard, documents, health, ocr, rag, sandbox, settings as settings_router, validation

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sovereignai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s v%s starting (env=%s)", settings.APP_NAME, settings.VERSION, settings.ENV)
    settings.ensure_dirs()
    init_db()
    # warm-up embedding provider in the background so the first query is fast
    try:
        from ai.embeddings import get_embedding_service

        service = get_embedding_service()
        service.embed_texts(["sovereignai warm-up"])
        logger.info("Embeddings ready: %s", service.provider_name)
    except Exception as exc:
        logger.warning("Embedding warm-up failed: %s", exc)
    yield
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Sovereign AI Workbench — secure document processing, OCR, RAG and agents (SIH 2026, SIH117).",
    lifespan=lifespan,
)

# CORS — only the configured frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN] + (
        ["http://localhost:5173", "http://127.0.0.1:5173"] if settings.ENV != "production" else []
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
    duration_ms = int((time.monotonic() - start) * 1000)
    if request.url.path.startswith("/api"):
        logger.info("%s %s -> %s (%dms)", request.method, request.url.path,
                    response.status_code, duration_ms)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


# --- Routers ---------------------------------------------------------------
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(ocr.router)
app.include_router(agents.router)
app.include_router(validation.router)
app.include_router(sandbox.router)
app.include_router(settings_router.router)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }