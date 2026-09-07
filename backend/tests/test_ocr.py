"""OCR tests — run against whichever local engine is available
(Tesseract or the bundled-ONNX RapidOCR fallback); skipped when neither is.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ocr.engine import ocr_available, ocr_engine_name, ocr_image, ocr_pdf

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

pytestmark = pytest.mark.skipif(not ocr_available(), reason="No OCR engine installed")


def test_ocr_image_extracts_text():
    result = ocr_image(str(SAMPLES / "land_record_scanned.png"))
    assert "Record" in result.text
    assert "Sunita" in result.text or "Patil" in result.text
    assert result.pages[0].page_number == 1
    assert result.engine in ("tesseract", "rapidocr")


def test_ocr_engine_name_matches():
    assert ocr_engine_name() in ("tesseract", "rapidocr-onnx")


def test_ocr_pdf_extracts_text():
    result = ocr_pdf(str(SAMPLES / "land_record_scanned.pdf"))
    assert len(result.pages) >= 1
    assert len(result.text) > 40


def test_ocr_image_returns_confidence():
    result = ocr_image(str(SAMPLES / "land_record_scanned.png"))
    assert result.pages[0].confidence >= 0