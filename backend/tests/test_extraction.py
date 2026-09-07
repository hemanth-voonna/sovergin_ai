"""Text extraction tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from document.extractor import clean_text, extract_text, needs_ocr

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_txt_extraction():
    doc = extract_text(str(SAMPLES / "land_record.txt"), "txt")
    assert doc.total_chars > 500
    assert "Sunita Vishnu Patil" in doc.full_text
    assert not doc.ocr_used
    assert len(doc.pages) == 1


def test_docx_extraction():
    doc = extract_text(str(SAMPLES / "land_record.docx"), "docx")
    assert "124/3" in doc.full_text
    assert doc.total_chars > 500


def test_pdf_extraction_text_layer():
    doc = extract_text(str(SAMPLES / "land_record.pdf"), "pdf")
    assert "Sunita Vishnu Patil" in doc.full_text
    assert not doc.ocr_used


def test_pdf_scanned_uses_ocr():
    from ocr.engine import ocr_available

    if not ocr_available():
        pytest.skip("Tesseract not installed")
    doc = extract_text(str(SAMPLES / "land_record_scanned.pdf"), "pdf")
    assert doc.ocr_used is True
    assert len(doc.full_text) > 40


def test_clean_text():
    assert clean_text("a\x00b\n\n\n\nc  d") == "ab\n\nc  d"
    assert clean_text("  spaced  out  ") == "spaced  out"


def test_needs_ocr():
    assert needs_ocr("")
    assert needs_ocr("   short   ")
    assert not needs_ocr("x" * 100)


def test_unsupported_type_raises(tmp_path):
    bad = tmp_path / "file.xyz"
    bad.write_text("hello")
    with pytest.raises(ValueError):
        extract_text(str(bad), "xyz")