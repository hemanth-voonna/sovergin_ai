"""Document management API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..activity import log_event
from ..config import settings
from ..schemas import DocumentDetailOut, DocumentListOut, DocumentOut
from ..security import ValidationError
from ..services import (
    create_document,
    delete_document,
    get_document,
    index_document,
    list_documents,
    process_document,
    run_full_pipeline,
    save_upload,
)
from . import deps  # noqa: F401  (register auth dependency)

router = APIRouter(prefix="/api/documents", tags=["documents"], dependencies=[deps.auth])


def _doc_out(doc) -> DocumentOut:
    return DocumentOut(**doc.to_dict())


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    try:
        storage_path, file_type = save_upload(file.filename or "upload.bin", content)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail)

    doc = create_document(
        filename=Path(storage_path).name,
        original_name=file.filename or "upload",
        content=content,
        file_type=file_type,
        storage_path=storage_path,
    )
    return _doc_out(doc)


@router.get("", response_model=DocumentListOut)
def list_all(limit: int = 100, offset: int = 0):
    docs, total = list_documents(limit=min(limit, 500), offset=max(offset, 0))
    return {"items": [_doc_out(d) for d in docs], "total": total}


@router.post("/sample", response_model=DocumentOut, status_code=201)
def load_sample():
    """Ingest the bundled sample land record so the demo starts in one click."""
    sample = Path(settings.SAMPLE_DIR) / "land_record.txt"
    if not sample.exists():
        raise HTTPException(status_code=404, detail="Sample document not found on server.")
    content = sample.read_bytes()
    storage_path, file_type = save_upload("land_record.txt", content)
    doc = create_document(
        filename=Path(storage_path).name,
        original_name="land_record_sample.txt",
        content=content,
        file_type=file_type,
        storage_path=storage_path,
    )
    return _doc_out(doc)


@router.get("/{doc_id}", response_model=DocumentDetailOut)
def get_one(doc_id: str):
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    data = doc.to_dict(include_text=True)
    pages = data.pop("pages_data") or []
    out = DocumentDetailOut(**data, pages=pages)
    return out


@router.delete("/{doc_id}", status_code=204)
def remove(doc_id: str):
    if not delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/{doc_id}/process", response_model=DocumentOut)
def process_one(doc_id: str):
    try:
        doc = process_document(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Processing failed: {exc}")
    return _doc_out(doc)


@router.post("/{doc_id}/index", response_model=DocumentOut)
def index_one(doc_id: str):
    try:
        doc = index_document(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Indexing failed: {exc}")
    return _doc_out(doc)


@router.post("/{doc_id}/pipeline", response_model=DocumentOut)
def pipeline_one(doc_id: str):
    """Process + index in one call (used by the demo 'one-click' flow)."""
    try:
        doc = run_full_pipeline(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Pipeline failed: {exc}")
    return _doc_out(doc)