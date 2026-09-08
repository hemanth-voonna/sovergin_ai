"""Generic document validation engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ValidationIssue:
    severity: str
    category: str
    field: str | None
    message: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "field": self.field,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    status: str = "valid"
    score: int = 100
    issues: list[ValidationIssue] = field(default_factory=list)
    fields: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "fields": self.fields,
        }


def _parse_date(value: str) -> datetime | None:
    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            pass

    return None


def _extract_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    patterns = {
        "record_number": r"(?:record\s*(?:no|number)|reference\s*(?:no|number))\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        "owner_name": r"(?:owner|owner\s+name)\s*[:#-]\s*([A-Za-z][A-Za-z .'-]{2,80})",
        "survey_number": r"(?:survey\s*(?:no|number)|s\s*no)\s*[:#-]?\s*([0-9]+[A-Za-z0-9/-]*)",
        "village": r"village\s*[:#-]\s*([A-Za-z][A-Za-z .'-]{2,60})",
        "district": r"district\s*[:#-]\s*([A-Za-z][A-Za-z .'-]{2,60})",
        "certificate_number": r"(?:certificate\s*(?:no|number)|cert\s*(?:no|number))\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        "application_number": r"(?:application\s*(?:no|number)|application\s*id)\s*[:#-]?\s*([A-Za-z0-9/-]+)",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "phone": r"(?:phone|mobile|contact)\s*(?:number|no)?\s*[:#-]?\s*(\+?[0-9][0-9 -]{8,14})",
        "document_date": r"(?:document\s*date|date\s*of\s*document|doc\s*date)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        "registration_date": r"(?:registration\s*date|registered\s*on|date\s*of\s*registration)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        "date_of_birth": r"(?:date\s*of\s*birth|dob)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        "land_area": r"(?:land\s*area|area)\s*[:#-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(hectares?|acres?|sq\.?\s*(?:m|ft|yards?)|gunthas?)",
    }

    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        if name == "land_area":
            fields[name] = f"{match.group(1)} {match.group(2)}"
        elif name == "email":
            fields[name] = match.group(0).strip()
        else:
            fields[name] = match.group(1).strip().rstrip(".,;")

    return fields


def _is_land_document(text: str, fields: dict[str, str]) -> bool:
    lower = text.lower()

    keywords = [
        "survey number",
        "survey no",
        "land area",
        "hectare",
        "acre",
        "village",
        "land record",
        "property record",
    ]

    keyword_count = sum(1 for word in keywords if word in lower)

    land_fields = {
        "survey_number",
        "village",
        "district",
        "land_area",
        "owner_name",
        "record_number",
    }

    field_count = len(land_fields.intersection(fields.keys()))

    return keyword_count >= 2 or field_count >= 3


def validate_text(
    text: str,
    filename: str | None = None,
) -> ValidationResult:

    text = text or ""
    issues: list[ValidationIssue] = []

    if not text.strip():
        issues.append(
            ValidationIssue(
                "error",
                "missing",
                None,
                "No readable text was extracted from the document.",
            )
        )

        return ValidationResult(
            status="invalid",
            score=0,
            issues=issues,
            fields={},
        )

    fields = _extract_fields(text)
    lower = text.lower()

    # ---------------------------------------------------------
    # Generic document checks
    # ---------------------------------------------------------

    if len(text.strip()) < 30:
        issues.append(
            ValidationIssue(
                "warning",
                "quality",
                None,
                "Very little readable text was extracted. OCR quality may be low.",
            )
        )

    if text.count("�") >= 3:
        issues.append(
            ValidationIssue(
                "warning",
                "quality",
                None,
                "Document contains several unreadable OCR characters.",
            )
        )

    # ---------------------------------------------------------
    # Date validation
    # ---------------------------------------------------------

    for field_name in (
        "document_date",
        "registration_date",
        "date_of_birth",
    ):
        value = fields.get(field_name)

        if not value:
            continue

        parsed = _parse_date(value)

        if parsed is None:
            issues.append(
                ValidationIssue(
                    "warning",
                    "format",
                    field_name,
                    f"Date '{value}' is not valid.",
                )
            )
        elif parsed.date() > datetime.now().date():
            issues.append(
                ValidationIssue(
                    "warning",
                    "format",
                    field_name,
                    f"Date '{value}' is in the future.",
                )
            )

    # ---------------------------------------------------------
    # Email
    # ---------------------------------------------------------

    email = fields.get("email")

    if email:
        if not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email,
        ):
            issues.append(
                ValidationIssue(
                    "warning",
                    "format",
                    "email",
                    f"Email address looks unusual: '{email}'.",
                )
            )

    # ---------------------------------------------------------
    # Phone
    # ---------------------------------------------------------

    phone = fields.get("phone")

    if phone:
        digits = re.sub(r"\D", "", phone)

        if len(digits) < 10:
            issues.append(
                ValidationIssue(
                    "warning",
                    "format",
                    "phone",
                    "Phone number appears incomplete.",
                )
            )

    # ---------------------------------------------------------
    # Suspicious words
    # ---------------------------------------------------------

    suspicious_words = [
        "fraud",
        "forged",
        "fake",
        "disputed",
        "litigation",
        "under investigation",
        "cancelled",
        "canceled",
        "pending",
        "rejected",
    ]

    for word in suspicious_words:
        if word in lower:
            issues.append(
                ValidationIssue(
                    "warning",
                    "suspicious",
                    None,
                    f"Document contains potentially significant keyword: '{word}'.",
                )
            )

    # ---------------------------------------------------------
    # Duplicate identifiers
    # ---------------------------------------------------------

    for field_name in (
        "record_number",
        "survey_number",
        "certificate_number",
        "application_number",
    ):
        value = fields.get(field_name)

        if value and lower.count(value.lower()) > 1:
            issues.append(
                ValidationIssue(
                    "warning",
                    "duplicate",
                    field_name,
                    f"Identifier '{value}' appears more than once.",
                )
            )

    # ---------------------------------------------------------
    # Land-specific checks
    # Only activated for land-like documents.
    # ---------------------------------------------------------

    if _is_land_document(text, fields):

        land_area = fields.get("land_area")

        if land_area:
            match = re.match(
                r"([0-9]+(?:\.[0-9]+)?)",
                land_area,
            )

            if match and float(match.group(1)) <= 0:
                issues.append(
                    ValidationIssue(
                        "error",
                        "format",
                        "land_area",
                        "Land area must be greater than zero.",
                    )
                )

    # ---------------------------------------------------------
    # Score
    # ---------------------------------------------------------

    errors = [
        issue for issue in issues
        if issue.severity == "error"
    ]

    warnings = [
        issue for issue in issues
        if issue.severity == "warning"
    ]

    score = max(
        0,
        100 - (25 * len(errors)) - (10 * len(warnings)),
    )

    if errors:
        status = "invalid"
    elif warnings:
        status = "warning"
    else:
        status = "valid"

    return ValidationResult(
        status=status,
        score=score,
        issues=issues,
        fields=fields,
    )