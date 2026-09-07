"""Tools available to agents.

Each tool is a small function with a schema; the orchestrator passes tool
results into the agent's prompt. Tools never execute code — the sandbox is
the only execution surface, and only via the Sandbox API.
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Document
from document.validator import validate_text
from rag.pipeline import get_rag_pipeline

TOOL_SCHEMAS: dict[str, dict] = {
    "read_document": {
        "name": "read_document",
        "description": "Get the full extracted text of a document by ID.",
        "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}},
    },
    "extract_fields": {
        "name": "extract_fields",
        "description": "Extract known land-record fields (owner, survey number, area...) from a document ID.",
        "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}},
    },
    "rag_search": {
        "name": "rag_search",
        "description": "Search the indexed document corpus and return grounded passages with sources.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "document_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "run_validation": {
        "name": "run_validation",
        "description": "Run the rule-based validation suite on a document.",
        "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}},
    },
}


def _get_document_text(document_id: str) -> str | None:
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        return doc.extracted_text if doc else None
    finally:
        db.close()


def tool_read_document(document_id: str) -> dict:
    text = _get_document_text(document_id)
    if text is None:
        return {"error": f"Document {document_id} not found or not processed."}
    return {"document_id": document_id, "text": text[:12_000]}


def tool_extract_fields(document_id: str) -> dict:
    text = _get_document_text(document_id)
    if text is None:
        return {"error": "Document not found or not processed."}
    result = validate_text(text)
    return {"document_id": document_id, "fields": result.fields}


def tool_rag_search(question: str, document_ids: list[str] | None = None) -> dict:
    answer = get_rag_pipeline().answer(question, document_ids=document_ids)
    return answer.to_dict()


def tool_run_validation(document_id: str) -> dict:
    text = _get_document_text(document_id)
    if text is None:
        return {"error": "Document not found or not processed."}
    return validate_text(text).to_dict()


def call_tool(name: str, **kwargs) -> dict:
    dispatch = {
        "read_document": tool_read_document,
        "extract_fields": tool_extract_fields,
        "rag_search": tool_rag_search,
        "run_validation": tool_run_validation,
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**kwargs)
    except Exception as exc:
        return {"error": f"Tool {name} failed: {exc}"}