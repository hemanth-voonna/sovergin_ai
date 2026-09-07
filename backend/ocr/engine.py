"""OCR engine — dual backend, fully local & offline.

Backends (first available wins):

  1. **Tesseract** (via pytesseract) — used when the binary is installed
     (e.g. inside the Docker image). Best multi-language support.
  2. **RapidOCR (ONNX)** — pure-Python fallback with models bundled inside the
     pip package (no downloads, no system install). Ideal for Windows hosts
     where installing Tesseract is undesirable.

Used for scanned PDFs and image uploads. Text-layer PDFs skip OCR and go
through direct extraction (see document/extractor.py).
"""
from __future__ import annotations

import importlib.util
import logging
import shutil
import time
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)

TESSERACT_CMD = shutil.which("tesseract")
RAPIDOCR_AVAILABLE = importlib.util.find_spec("rapidocr_onnxruntime") is not None

_rapid_engine = None  # lazy singleton


@dataclass
class OCRPage:
    page_number: int
    text: str
    confidence: float = 0.0


@dataclass
class OCRResult:
    text: str
    pages: list[OCRPage] = field(default_factory=list)
    language: str = settings.OCR_LANG
    engine: str = "tesseract"
    took_ms: int = 0


def ocr_available() -> bool:
    return TESSERACT_CMD is not None or RAPIDOCR_AVAILABLE


def ocr_engine_name() -> str | None:
    """Name of the engine that would be used, or None if OCR is unavailable."""
    if TESSERACT_CMD is not None:
        return "tesseract"
    if RAPIDOCR_AVAILABLE:
        return "rapidocr-onnx"
    return None


def _get_rapid_engine():
    """Lazily initialise the RapidOCR engine (heavy import, done once)."""
    global _rapid_engine
    if _rapid_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _rapid_engine = RapidOCR()
    return _rapid_engine


def _ocr_pil_tesseract(image, lang: str) -> tuple[str, float]:
    """OCR one PIL image with Tesseract -> (text, mean confidence)."""
    import pytesseract

    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    words, confidences = data["text"], data["conf"]
    parts: list[str] = []
    confs: list[float] = []
    for word, conf in zip(words, confidences):
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = -1.0
        if str(word).strip():
            parts.append(str(word))
            confs.append(conf)
    text = " ".join(parts)
    mean_conf = (sum(confs) / len(confs)) if confs else 0.0
    return text, mean_conf


def _ocr_pil_rapid(image) -> tuple[str, float]:
    """OCR one PIL image with RapidOCR -> (text, mean confidence).

    Lines are emitted top-to-bottom (ordered by bounding box position) so the
    layout of a land record stays readable and searchable.
    """
    import numpy as np

    engine = _get_rapid_engine()
    arr = np.asarray(image.convert("RGB"))[:, :, ::-1].copy()  # RGB -> BGR ndarray
    result, _ = engine(arr)

    lines: list[tuple[float, float, str, float]] = []
    if result:
        for box, text, score in result:
            if not text or not str(text).strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append((min(ys), min(xs), str(text).strip(), float(score)))
    lines.sort(key=lambda t: (t[0], t[1]))  # top-to-bottom, left-to-right

    if not lines:
        return "", 0.0
    text = "\n".join(ln[2] for ln in lines)
    conf = sum(ln[3] for ln in lines) / len(lines)
    return text, conf


def _ocr_pil_image(image, lang: str) -> tuple[str, float, str]:
    """OCR one PIL image using whichever engine is available."""
    if TESSERACT_CMD is not None:
        text, conf = _ocr_pil_tesseract(image, lang)
        return text, conf, "tesseract"
    if RAPIDOCR_AVAILABLE:
        text, conf = _ocr_pil_rapid(image)
        return text, conf, "rapidocr"
    raise RuntimeError(
        "No OCR engine is available. Install Tesseract on the system or run "
        "inside Docker (or: pip install rapidocr-onnxruntime)."
    )


def ocr_image(image_path: str, lang: str | None = None) -> OCRResult:
    """OCR a single image file."""
    if not ocr_available():
        raise RuntimeError(
            "No OCR engine is available (install Tesseract, run inside Docker, "
            "or pip install rapidocr-onnxruntime)."
        )
    from PIL import Image

    lang = lang or settings.OCR_LANG
    start = time.monotonic()
    image = Image.open(image_path)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    text, conf, engine = _ocr_pil_image(image, lang)
    return OCRResult(
        text=text.strip(),
        pages=[OCRPage(page_number=1, text=text.strip(), confidence=round(conf, 2))],
        language=lang,
        engine=engine,
        took_ms=int((time.monotonic() - start) * 1000),
    )


def ocr_pdf(pdf_path: str, lang: str | None = None, dpi: int | None = None,
            pages: list[int] | None = None) -> OCRResult:
    """Render PDF pages to images and OCR them."""
    if not ocr_available():
        raise RuntimeError(
            "No OCR engine is available (install Tesseract, run inside Docker, "
            "or pip install rapidocr-onnxruntime)."
        )
    import fitz  # PyMuPDF

    from PIL import Image

    lang = lang or settings.OCR_LANG
    dpi = dpi or settings.OCR_DPI
    start = time.monotonic()

    doc = fitz.open(pdf_path)
    page_numbers = pages or list(range(doc.page_count))
    ocr_pages: list[OCRPage] = []
    all_text: list[str] = []
    engine = "tesseract"
    zoom = dpi / 72.0
    for pno in page_numbers:
        page = doc[pno]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        text, conf, engine = _ocr_pil_image(img, lang)
        ocr_pages.append(OCRPage(page_number=pno + 1, text=text, confidence=round(conf, 2)))
        if text.strip():
            all_text.append(text)
    doc.close()

    return OCRResult(
        text="\n\n".join(t for t in all_text if t.strip()),
        pages=ocr_pages,
        language=lang,
        engine=engine,
        took_ms=int((time.monotonic() - start) * 1000),
    )
