"""Central application configuration.

All values come from environment variables (or a local `.env` file).
No secrets are hard-coded; API keys live only on the backend.

Sovereign/offline defaults:
  * The LLM defaults to the built-in grounded engine (no network, no model).
  * Embeddings default to a fully local ONNX model when it is cached on the
    machine, and transparently fall back to zero-download hash embeddings.
  * Chroma telemetry is disabled (this module runs before any `chromadb`
    import, so the environment variable below is always in effect).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Chroma collects anonymized product telemetry by default. The backend must
# never phone home, so disable it before chromadb is ever imported. The vector
# store additionally passes Settings(anonymized_telemetry=False) as belt & braces.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    APP_NAME: str = "SovereignAI Workbench"
    VERSION: str = "1.0.0"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Storage ---
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    VECTOR_DB_PATH: str = "./data/chroma"
    SAMPLE_DIR: str = "./samples"

    # --- Database (PostgreSQL in Docker, SQLite for local dev) ---
    DATABASE_URL: str = "sqlite:///./data/sovereignai.db"

    # --- Security ---
    MAX_UPLOAD_MB: int = 25
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt,png,jpg,jpeg"
    ACCESS_TOKEN: str = ""  # optional bearer token; empty = open (trusted network)
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- LLM (local-only by design; cloud endpoints are refused by default) ---
    # auto | builtin | mock | ollama | openai-compatible (see ai/llm.py)
    LLM_PROVIDER: str = "auto"
    # Only used when a local OpenAI-compatible endpoint is configured; with the
    # default built-in engine it is inert. Neutral name to avoid implying cloud.
    LLM_MODEL: str = "local-llm"
    # API key for a *local* OpenAI-compatible server (Ollama, vLLM, LM Studio...).
    # Ignored unless OPENAI_BASE_URL points at an allowed endpoint.
    OPENAI_API_KEY: str = ""
    # Base URL of a LOCAL OpenAI-compatible chat endpoint.
    # Empty = built-in grounded engine. Non-loopback hosts are refused unless
    # ALLOW_REMOTE_LLM=true (explicit opt-in; still never defaults to any cloud).
    OPENAI_BASE_URL: str = ""
    ALLOW_REMOTE_LLM: bool = False
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1024

    # --- Embeddings (always computed locally; never an external API) ---
    # auto   -> ONNX all-MiniLM-L6-v2 when cached locally, else hash fallback
    # chroma -> same ONNX model (errors clearly if not provisioned locally)
    # hash   -> deterministic hashing embeddings (zero model, fully offline)
    EMBEDDINGS_PROVIDER: str = "auto"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- OCR ---
    OCR_LANG: str = "eng"
    OCR_DPI: int = 220

    # --- RAG ---
    RAG_TOP_K: int = 5
    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 120

    # --- Sandbox ---
    SANDBOX_EXECUTOR: str = "subprocess"  # subprocess | docker
    SANDBOX_TIMEOUT_SECONDS: int = 15
    SANDBOX_MEMORY_MB: int = 256

    # ---------------------------------------------------------------
    @property
    def allowed_extensions(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",") if e.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def auth_enabled(self) -> bool:
        return bool(self.ACCESS_TOKEN.strip())

    def ensure_dirs(self) -> None:
        for d in (self.DATA_DIR, self.UPLOAD_DIR, self.VECTOR_DB_PATH):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()

# Make the current working directory importable (backend/ is the python root)
if __name__ != "__main__":
    os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parent.parent))