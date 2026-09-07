"""Document service — orchestrates the ingestion pipeline:

upload -> validate -> extract text -> OCR if needed -> clean -> chunk
-> embeddings -> vector store -> ready for RAG
"""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from sqlalchemy import func, select

from ai.embeddings import get_embedding_service
from document.extractor import extract_text
from document.validator import validate_text
from rag.chunker import chunk_pages
from rag.vectorstore import get_vector_store
from .activity import log_event
from .config import settings
from .database import SessionLocal
from .models import Document
from .security import sha256_bytes, validate_upload

logger = logging.getLogger(__name__)


def save_upload(filename: str, content: bytes) -> tuple[str, str]:
    """Validate + persist an upload. Returns (storage_path, file_type)."""
    file_type = validate_upload(filename, content)
    storage_name = f"{uuid.uuid4().hex}.{file_type}"
    path = Path(settings.UPLOAD_DIR) / storage_name
    path.write_bytes(content)
    return str(path), file_type


def create_document(filename: str, original_name: str, content: bytes,
                    file_type: str, storage_path: str) -> Document:
    db = SessionLocal()
    try:
        doc = Document(
            filename=filename,
            original_name=original_name,
            file_type=file_type,
            size_bytes=len(content),
            checksum=sha256_bytes(content),
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        log_event(
            "upload", f"Document uploaded: {original_name}",
            entity_type="document", entity_id=doc.id,
            details={"filename": original_name, "size_bytes": len(content), "type": file_type},
        )
        return doc
    finally:
        db.close()


def get_document(doc_id: str) -> Document | None:
    db = SessionLocal()
    try:
        return db.get(Document, doc_id)
    finally:
        db.close()


def list_documents(limit: int = 100, offset: int = 0) -> tuple[list[Document], int]:
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Document.id))) or 0
        rows = db.scalars(
            select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return list(rows), total
    finally:
        db.close()


def delete_document(doc_id: str) -> bool:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return False
        name = doc.original_name or doc.filename
        db.delete(doc)
        db.commit()
        get_vector_store().delete_document(doc_id)
        log_event("delete", f"Document deleted: {name}", entity_type="document", entity_id=doc_id)
        return True
    finally:
        db.close()


def process_document(doc_id: str) -> Document:
    """Extract + clean text (OCR when needed). Does NOT index vectors."""
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise ValueError("Document not found")
        doc.status = "processing"
        doc.error_message = None
        db.commit()

        storage_path = Path(settings.UPLOAD_DIR) / doc.filename
        if not storage_path.exists():
            raise FileNotFoundError(f"Stored file missing: {doc.filename}")

        extracted = extract_text(str(storage_path), doc.file_type)
        doc.ocr_used = extracted.ocr_used
        doc.page_count = len(extracted.pages)
        doc.char_count = extracted.total_chars
        doc.extracted_text = extracted.full_text
        doc.pages_data = [
            {
                "page_number": p.page_number,
                "text": p.text,
                "source": p.source,
                "confidence": p.confidence,
            }
            for p in extracted.pages
        ]
        doc.status = "processed"

        validation = validate_text(extracted.full_text, doc.original_name)
        doc.validation_status = validation.status

        db.commit()
        db.refresh(doc)
        log_event(
            "process", f"Document processed: {doc.original_name} "
                       f"({doc.page_count} pages, {doc.char_count} chars"
                       + (", OCR used" if doc.ocr_used else "") + ")",
            entity_type="document", entity_id=doc.id,
            details={"pages": doc.page_count, "chars": doc.char_count, "ocr": doc.ocr_used},
        )
        return doc
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "failed"
            doc.error_message = str(exc)[:1000]
            db.commit()
        log_event("process", f"Processing failed: {exc}", entity_type="document", entity_id=doc_id)
        raise
    finally:
        db.close()


def index_document(doc_id: str) -> Document:
    """Chunk + embed + store vectors."""
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            raise ValueError("Document not found")
        if doc.status not in ("processed", "indexed"):
            raise ValueError(
                f"Document must be processed before indexing (current status: {doc.status})."
            )
        if doc.extracted_text is None or not doc.extracted_text.strip():
            raise ValueError("Document has no extracted text; run OCR/processing first.")

        pages = [(p.page_number, p.text) for p in _document_pages(doc)]
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("No chunks could be generated from the document text.")

        doc.status = "indexing"
        db.commit()

        embeddings = get_embedding_service().embed_texts([c.text for c in chunks])
        vectorstore = get_vector_store()
        vectorstore.delete_document(doc_id)  # idempotent re-index
        n = vectorstore.add_chunks(doc.id, doc.original_name or doc.filename, chunks, embeddings)

        doc.chunk_count = n
        doc.status = "indexed"
        db.commit()
        db.refresh(doc)
        log_event(
            "index", f"Document indexed: {doc.original_name} ({n} chunks)",
            entity_type="document", entity_id=doc.id, details={"chunks": n},
        )
        return doc
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "failed"
            doc.error_message = str(exc)[:1000]
            db.commit()
        log_event("index", f"Indexing failed: {exc}", entity_type="document", entity_id=doc_id)
        raise
    finally:
        db.close()


def _document_pages(doc: Document) -> list:
    """Rebuild page list from stored per-page data."""
    from document.extractor import PageText

    if doc.pages_data:
        return [
            PageText(
                page_number=int(p.get("page_number", i + 1)),
                text=str(p.get("text", "")),
                source=str(p.get("source", "text")),
                confidence=p.get("confidence"),
            )
            for i, p in enumerate(doc.pages_data)
        ]
    text = doc.extracted_text or ""
    return [PageText(page_number=1, text=text, source="ocr" if doc.ocr_used else "text")]


def run_full_pipeline(doc_id: str) -> Document:
    process_document(doc_id)
    return index_document(doc_id)


def get_document_stats() -> dict[str, int]:
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Document.id))) or 0
        processed = db.scalar(
            select(func.count(Document.id)).where(Document.status.in_(["processed", "indexed"]))
        ) or 0
        indexed = db.scalar(
            select(func.count(Document.id)).where(Document.status == "indexed")
        ) or 0
        ocr = db.scalar(select(func.count(Document.id)).where(Document.ocr_used.is_(True))) or 0
        failed = db.scalar(
            select(func.count(Document.id)).where(Document.status == "failed")
        ) or 0
        return {
            "total": total,
            "processed": processed,
            "indexed": indexed,
            "ocr": ocr,
            "failed": failed,
            "pending": max(0, total - processed - failed),
        }
    finally:
        db.close()