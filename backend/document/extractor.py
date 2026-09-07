"""Text extraction.

PDFs with a text layer use direct extraction; scanned PDFs and images fall
back to OCR automatically.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field

from ocr.engine import OCRPage, ocr_image, ocr_pdf

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 40  # below this, a PDF page is treated as scanned


@dataclass
class PageText:
    page_number: int
    text: str
    source: str = "text"  # text | ocr
    confidence: float | None = None


@dataclass
class ExtractedDocument:
    pages: list[PageText] = field(default_factory=list)
    ocr_used: bool = False
    total_chars: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    def to_dict(self) -> dict:
        return {
            "pages": [
                {
                    "page_number": p.page_number,
                    "text": p.text,
                    "source": p.source,
                    "confidence": p.confidence,
                }
                for p in self.pages
            ],
            "ocr_used": self.ocr_used,
            "total_chars": self.total_chars,
        }


def clean_text(text: str) -> str:
    """Normalise whitespace, drop control chars, NFC-normalise unicode."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\x00", "")
    lines = [ln.rstrip() for ln in text.splitlines()]
    # collapse 3+ blank lines to one
    out: list[str] = []
    blanks = 0
    for ln in lines:
        if not ln.strip():
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(ln)
    return "\n".join(out).strip()


def needs_ocr(text: str) -> bool:
    return len(text.strip()) < MIN_TEXT_CHARS


def _extract_pdf(path: str) -> tuple[list[PageText], bool]:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    pages: list[PageText] = []
    ocr_used = False
    try:
        for pno in range(doc.page_count):
            raw = doc[pno].get_text("text")
            if needs_ocr(raw):
                logger.info("PDF page %d has no text layer; running OCR.", pno + 1)
                ocr_pages = ocr_pdf(path, pages=[pno]).pages
                if ocr_pages:
                    p = ocr_pages[0]
                    pages.append(
                        PageText(
                            page_number=pno + 1,
                            text=clean_text(p.text),
                            source="ocr",
                            confidence=p.confidence,
                        )
                    )
                ocr_used = True
            else:
                pages.append(
                    PageText(page_number=pno + 1, text=clean_text(raw), source="text")
                )
    finally:
        doc.close()
    return pages, ocr_used


def _extract_docx(path: str) -> list[PageText]:
    from docx import Document as DocxDocument

    doc = DocxDocument(path)
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return [PageText(page_number=1, text=clean_text("\n".join(parts)), source="text")]


def _extract_txt(path: str) -> list[PageText]:
    raw = None
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as fh:
                raw = fh.read()
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raw = open(path, "r", encoding="utf-8", errors="replace").read()
    return [PageText(page_number=1, text=clean_text(raw), source="text")]


def extract_text(path: str, file_type: str) -> ExtractedDocument:
    """Extract text for any supported file type, using OCR when necessary."""
    file_type = file_type.lower()
    if file_type == "pdf":
        pages, ocr_used = _extract_pdf(path)
    elif file_type == "docx":
        pages = _extract_docx(path)
        ocr_used = False
    elif file_type == "txt":
        pages = _extract_txt(path)
        ocr_used = False
    elif file_type in ("png", "jpg", "jpeg"):
        result = ocr_image(path)
        pages = [
            PageText(
                page_number=p.page_number,
                text=clean_text(p.text),
                source="ocr",
                confidence=p.confidence,
            )
            for p in result.pages
        ]
        ocr_used = True
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    total = sum(len(p.text) for p in pages)
    return ExtractedDocument(pages=pages, ocr_used=ocr_used, total_chars=total)