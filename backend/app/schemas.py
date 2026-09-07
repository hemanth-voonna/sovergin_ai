"""Pydantic request/response schemas. These double as the API contract with the frontend."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ Documents
class DocumentOut(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    size_bytes: int
    checksum: str
    status: str
    error_message: str | None = None
    ocr_used: bool = False
    page_count: int = 0
    char_count: int = 0
    chunk_count: int = 0
    validation_status: str = "pending"
    created_at: str | None = None
    updated_at: str | None = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class PageOut(BaseModel):
    page_number: int
    text: str
    source: str = "text"  # text | ocr
    confidence: float | None = None


class DocumentDetailOut(DocumentOut):
    pages: list[PageOut] = []
    extracted_text: str | None = None


# ------------------------------------------------------------------ RAG
class RAGQueryIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    document_ids: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    document_id: str
    filename: str
    page: int | None = None
    chunk_index: int | None = None
    score: float | None = None
    snippet: str = ""


class RAGAnswerOut(BaseModel):
    question: str
    answer: str
    grounded: bool = True
    sources: list[SourceOut] = []
    model: str = ""
    took_ms: int = 0
    mode: str = "llm"  # llm | extractive


# ------------------------------------------------------------------ OCR
class OCRRequestIn(BaseModel):
    document_id: str | None = None
    language: str | None = None


class OCRPageOut(BaseModel):
    page_number: int
    text: str
    confidence: float


class OCRResultOut(BaseModel):
    text: str
    pages: list[OCRPageOut] = []
    language: str
    engine: str = "tesseract"
    took_ms: int = 0


# ------------------------------------------------------------------ Agents
class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    input_schema: dict[str, Any]
    output: str
    tools: list[str]
    instructions: str
    requires_llm: bool = False


class AgentRunIn(BaseModel):
    agent_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class AgentRunOut(BaseModel):
    agent_id: str
    status: str  # completed | error
    output: dict[str, Any]
    logs: list[str] = []
    took_ms: int = 0
    mode: str = "llm"  # llm | rule_based


# ------------------------------------------------------------------ Validation
class ValidationIssue(BaseModel):
    severity: str  # error | warning
    category: str
    field: str | None = None
    message: str


class ValidationResultOut(BaseModel):
    document_id: str
    status: str  # valid | warning | invalid
    score: int = 100  # 0-100
    issues: list[ValidationIssue] = []
    fields: dict[str, Any] = Field(default_factory=dict)
    took_ms: int = 0


# ------------------------------------------------------------------ Sandbox
class SandboxRunIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = "python"  # python | bash
    timeout: int | None = Field(default=None, ge=1, le=60)
    memory_mb: int | None = Field(default=None, ge=16, le=1024)


class SandboxRunOut(BaseModel):
    status: str  # completed | timed_out | error | killed
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    language: str = "python"
    log: list[str] = []


# ------------------------------------------------------------------ Dashboard / health
class HealthOut(BaseModel):
    status: str = "ok"
    version: str = ""
    uptime_s: float = 0
    cpu_percent: float = 0
    memory: dict[str, Any] = Field(default_factory=dict)
    disk: dict[str, Any] = Field(default_factory=dict)
    services: dict[str, Any] = Field(default_factory=dict)


class DashboardOut(BaseModel):
    documents: dict[str, int] = Field(default_factory=dict)
    rag_queries: int = 0
    agent_runs: int = 0
    sandbox_runs: int = 0
    vectors_indexed: int = 0
    health: dict[str, Any] = Field(default_factory=dict)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)
    activity_series: list[dict[str, Any]] = Field(default_factory=list)


class SettingsOut(BaseModel):
    llm_provider: str
    llm_model: str
    llm_configured: bool
    embedding_provider: str
    embedding_model: str
    vector_db: str
    ocr_lang: str
    max_upload_mb: int
    auth_enabled: bool
    sandbox_executor: str
    chunk_size: int
    chunk_overlap: int
    top_k: int