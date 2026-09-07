"""OCR layer: Tesseract-based extraction for images and scanned PDFs."""

from .engine import OCRPage, OCRResult, ocr_image, ocr_pdf, ocr_available

__all__ = ["OCRPage", "OCRResult", "ocr_image", "ocr_pdf", "ocr_available"]