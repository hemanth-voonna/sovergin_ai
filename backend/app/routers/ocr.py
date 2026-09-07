"""OCR API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..activity import log_event
from ..config import settings
from ocr.engine import ocr_available, ocr_image, ocr_pdf
from ..schemas import OCRResultOut
from ..services import get_document, save_upload
from . import deps  # noqa: F401

router = APIRouter(prefix="/api/ocr", tags=["ocr"], dependencies=[deps.auth])


@router.post("/process", response_model=OCRResultOut)
async def ocr_process(
    file: UploadFile | None = File(None),
    document_id: str | None = Query(None, description="ID of an already-uploaded PDF/image"),
    language: str | None = Query(None, description="Tesseract language code, e.g. eng/hin/mar"),
):
    if not document_id and file is None:
        raise HTTPException(status_code=400, detail="Provide a file or a document_id.")
    if not ocr_available():
        raise HTTPException(
            status_code=503,
            detail="No OCR engine is available. Install Tesseract, run inside Docker, "
                   "or pip install rapidocr-onnxruntime.",
        )
    language = language or settings.OCR_LANG

    if document_id:
        doc = get_document(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        path = Path(settings.UPLOAD_DIR) / doc.filename
        if doc.file_type == "pdf":
            result = ocr_pdf(str(path), lang=language)
        elif doc.file_type in ("png", "jpg", "jpeg"):
            result = ocr_image(str(path), lang=language)
        else:
            raise HTTPException(status_code=400, detail="OCR supports PDF and image files only.")
        label = doc.original_name
    elif file is not None:
        content = await file.read()
        storage_path, file_type = save_upload(file.filename or "upload.bin", content)
        label = file.filename or "upload"
        if file_type == "pdf":
            result = ocr_pdf(storage_path, lang=language)
        elif file_type in ("png", "jpg", "jpeg"):
            result = ocr_image(storage_path, lang=language)
        else:
            raise HTTPException(status_code=400, detail="OCR supports PDF and image files only.")
    log_event(
        "ocr", f"OCR completed on {label} ({len(result.pages)} page(s), {result.engine})",
        details={"pages": len(result.pages), "chars": len(result.text),
                 "lang": language, "engine": result.engine},
    )
    return OCRResultOut(
        text=result.text,
        pages=[
            {"page_number": p.page_number, "text": p.text, "confidence": p.confidence}
            for p in result.pages
        ],
        language=result.language,
        engine=result.engine,
        took_ms=result.took_ms,
    )