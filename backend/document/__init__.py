"""Document layer: extraction, cleaning and validation."""

from .extractor import ExtractedDocument, extract_text, needs_ocr
from .validator import ValidationIssue, ValidationResult, validate_text

__all__ = [
    "ExtractedDocument",
    "extract_text",
    "needs_ocr",
    "ValidationIssue",
    "ValidationResult",
    "validate_text",
]