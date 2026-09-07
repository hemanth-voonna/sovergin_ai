"""Document validation API."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from ..activity import log_event
from document.validator import validate_text
from ..schemas import ValidationResultOut
from ..services import get_document
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/validation", tags=["validation"], dependencies=[deps.auth])


@router.post("/check", response_model=ValidationResultOut)
def validation_check(payload: dict):
    doc_id = (payload or {}).get("document_id") or ""
    if not doc_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.extracted_text:
        raise HTTPException(status_code=409, detail="Document has no extracted text yet — process it first.")

    start = time.monotonic()
    result = validate_text(doc.extracted_text, doc.original_name)
    took = int((time.monotonic() - start) * 1000)
    log_event(
        "validation",
        f"Validation of {doc.original_name}: {result.status.upper()} "
        f"({len(result.issues)} issues)",
        entity_type="document", entity_id=doc_id,
        details={"status": result.status, "score": result.score, "issues": len(result.issues)},
    )
    return ValidationResultOut(
        document_id=doc_id,
        status=result.status,
        score=result.score,
        issues=[i.to_dict() for i in result.issues],
        fields=result.fields,
        took_ms=took,
    )