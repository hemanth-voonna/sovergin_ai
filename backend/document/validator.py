"""Document validation.

Rule-based checks for land-record style government documents:
required fields, formats, consistency, duplicates and suspicious values.

Result status: valid | warning | invalid, with a list of issues and an
optional LLM-generated explanation (added at the API layer).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

REQUIRED_FIELDS = [
    ("record_number", "Record number"),
    ("owner_name", "Owner name"),
    ("survey_number", "Survey number"),
    ("village", "Village"),
    ("district", "District"),
    ("land_area", "Land area"),
    ("document_date", "Document date"),
]

FIELD_PATTERNS: dict[str, list[re.Pattern]] = {
    "record_number": [
        re.compile(r"record\s*(?:no\.?|number)?\s*[:#-]\s*([A-Za-z0-9\-/]{3,30})", re.I),
    ],
    "owner_name": [
        re.compile(r"(?<![A-Za-z-])(?:registered\s+)?owner(?:\s*name)?\s*[:#-]?\s*([A-Za-z][A-Za-z. ]{2,80})", re.I),
    ],
    "survey_number": [
        re.compile(r"(?:survey\s*(?:no\.?|number)?|s\.?\s*no\.?)\s*[:#-]?\s*([0-9]+(?:[A-Za-z]?(?:/[A-Za-z0-9]+)?)?)", re.I),
    ],
    "village": [
        re.compile(r"village\s*[:#-]?\s*([A-Za-z][A-Za-z ]{2,60})", re.I),
    ],
    "district": [
        re.compile(r"district\s*[:#-]?\s*([A-Za-z][A-Za-z ]{2,60})", re.I),
    ],
    "land_area": [
        re.compile(r"(?:land\s*area|area)\s*[:#-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(hectares?|acres?|sq\.?\s*(?:m|ft|yards?)|gunthas?)", re.I),
    ],
    "document_date": [
        re.compile(r"(?:document\s*date|date\s*of\s*document|doc\.?\s*date)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I),
        re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b"),
    ],
    "registration_date": [
        re.compile(r"(?:registration\s*date|registered\s*on|date\s*of\s*registration)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I),
    ],
}


@dataclass
class ValidationIssue:
    severity: str  # error | warning
    category: str  # missing | format | consistency | duplicate | suspicious
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
    status: str = "valid"  # valid | warning | invalid
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


def _to_hectares(value: float, unit: str) -> float | None:
    unit = unit.lower().rstrip("s")
    factors = {
        "hectare": 1.0,
        "acre": 1.0 / 2.47105,
        "sq m": 1.0 / 10000.0,
        "sq ft": 1.0 / 107639.0,
        "sq yard": 1.0 / 11959.9,
        "guntha": 0.0101171,
    }
    return value * factors.get(unit, 0) if factors.get(unit, 0) else None


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _extract_fields(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for field, patterns in FIELD_PATTERNS.items():
        for pat in patterns:
            m = pat.search(text)
            if m:
                value = m.group(1).strip().rstrip(".,;")
                # for area, keep the unit, e.g. "2.35 hectares"
                if field == "land_area" and m.lastindex and m.lastindex >= 2 and m.group(2):
                    value = f"{value} {m.group(2)}"
                found[field] = value
                break
    return found


def validate_text(text: str, filename: str | None = None) -> ValidationResult:
    issues: list[ValidationIssue] = []
    fields = _extract_fields(text)
    lowered = text.lower()

    # --- 1. Required fields -------------------------------------------------
    for key, label in REQUIRED_FIELDS:
        value = fields.get(key, "")
        if not value:
            issues.append(
                ValidationIssue("error", "missing", key, f"Required field missing: {label}.")
            )

    # --- 2. Format checks ----------------------------------------------------
    area = fields.get("land_area")
    if area:
        num = re.match(r"([0-9]+(?:\.[0-9]+)?)", area)
        if num and float(num.group(1)) <= 0:
            issues.append(
                ValidationIssue("error", "format", "land_area",
                                f"Land area must be greater than zero (got '{area}').")
            )
    if fields.get("owner_name"):
        name = fields["owner_name"]
        if any(ch.isdigit() for ch in name):
            issues.append(
                ValidationIssue("warning", "format", "owner_name",
                                f"Owner name looks unusual (contains digits): '{name}'.")
            )
    date_raw = fields.get("document_date")
    if date_raw:
        parsed = _parse_date(date_raw)
        if parsed is None:
            issues.append(
                ValidationIssue("error", "format", "document_date",
                                f"Document date '{date_raw}' is not a valid dd/mm/yyyy date.")
            )
        elif parsed.date() > datetime.now().date():
            issues.append(
                ValidationIssue("error", "format", "document_date",
                                f"Document date '{date_raw}' is in the future.")
            )
    reg_raw = fields.get("registration_date")
    if reg_raw:
        reg = _parse_date(reg_raw)
        if reg is None:
            issues.append(
                ValidationIssue("warning", "format", "registration_date",
                                f"Registration date '{reg_raw}' is not a valid date.")
            )

    # --- 3. Consistency ------------------------------------------------------
    if date_raw and reg_raw:
        doc_d = _parse_date(date_raw)
        reg_d = _parse_date(reg_raw)
        if doc_d and reg_d and reg_d < doc_d:
            issues.append(
                ValidationIssue(
                    "warning", "consistency", "document_date",
                    f"Registration date ({reg_raw}) is earlier than document date ({date_raw}).",
                )
            )
    area_mentions = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(hectares?|acres?|sq\.?\s*(?:m|ft|yards?)|gunthas?)", lowered)
    converted = [_to_hectares(float(a), u) for a, u in area_mentions if _to_hectares(float(a), u)]
    if converted and (max(converted) - min(converted)) / max(converted) > 0.02:
        issues.append(
            ValidationIssue(
                "warning", "consistency", "land_area",
                f"Land area values conflict after unit conversion: {sorted(round(c, 4) for c in converted)} ha.",
            )
        )

    # --- 4. Duplicates --------------------------------------------------------
    rec = fields.get("record_number")
    if rec and lowered.count(rec.lower()) > 1:
        issues.append(
            ValidationIssue("warning", "duplicate", "record_number",
                            f"Record number '{rec}' appears more than once in the document.")
        )
    owner = fields.get("owner_name")
    if owner:
        owner_hits = re.findall(
            r"(?<![A-Za-z-])(?:registered\s+)?owner(?:\s*name)?\s*[:#-]?\s*([A-Za-z][A-Za-z. ]{2,80})",
            text, re.I,
        )
        unique_owners = {o.strip().lower() for o in owner_hits}
        if len(unique_owners) > 1:
            issues.append(
                ValidationIssue(
                    "warning", "duplicate", "owner_name",
                    f"Multiple owner names found in one record: {sorted(unique_owners)}.",
                )
            )

    # --- 5. Suspicious ---------------------------------------------------------
    suspicious_words = ["pending", "disputed", "litigation", "under investigation", "fraud"]
    for word in suspicious_words:
        if word in lowered:
            issues.append(
                ValidationIssue("warning", "suspicious", None,
                                f"Document contains a suspicious status keyword: '{word}'.")
            )
    if re.search(r"(?:owner|area|survey|record|date)[^.\n]{0,50}\b(nil|none|n/a|na)\b", lowered):
        issues.append(
            ValidationIssue("warning", "suspicious", None,
                            "A required field is marked 'NIL/None' instead of holding a value.")
        )

    # --- Score & status ---------------------------------------------------------
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    score = max(0, 100 - 25 * len(errors) - 10 * len(warnings))
    if errors:
        status = "invalid"
    elif warnings:
        status = "warning"
    else:
        status = "valid"

    return ValidationResult(status=status, score=score, issues=issues, fields=fields)