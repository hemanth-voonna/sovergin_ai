"""Document validation rule tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from document.validator import validate_text

SAMPLE = Path(__file__).resolve().parent.parent / "samples"


def _read(name: str) -> str:
    return (SAMPLE / name).read_text(encoding="utf-8")


def test_clean_sample_is_valid():
    result = validate_text(_read("land_record.txt"))
    assert result.status == "valid"
    assert result.score == 100
    assert result.issues == []
    assert result.fields["owner_name"] == "Mrs. Sunita Vishnu Patil"
    assert result.fields["survey_number"] == "124/3"
    assert result.fields["village"] == "Kamalpur"
    assert result.fields["district"] == "Nashik"
    assert result.fields["land_area"].startswith("2.35")
    assert result.fields["document_date"] == "15/08/2023"
    assert result.fields["record_number"] == "RL-2023-04512"


def test_issues_sample_is_invalid():
    result = validate_text(_read("land_record_with_issues.txt"))
    assert result.status == "invalid"
    assert result.score < 100
    categories = {i.category for i in result.issues}
    assert "missing" in categories          # district + area missing
    assert "format" in categories           # future date
    assert "duplicate" in categories        # record number twice / two owners
    assert any(i.field == "district" for i in result.issues)
    assert any(i.field == "land_area" for i in result.issues)
    assert any(i.field == "document_date" for i in result.issues)


def test_missing_required_fields():
    result = validate_text("Some random text with no record fields here at all.")
    assert result.status == "invalid"
    missing = {i.field for i in result.issues if i.category == "missing"}
    assert missing == {
        "record_number", "owner_name", "survey_number", "village",
        "district", "land_area", "document_date",
    }


def test_future_date_rejected():
    text = _read("land_record.txt").replace("15/08/2023", "15/12/2029")
    result = validate_text(text)
    assert result.status == "invalid"
    assert any(i.field == "document_date" and i.severity == "error" for i in result.issues)


def test_zero_area_rejected():
    text = _read("land_record.txt").replace("2.35 hectares", "0 hectares")
    result = validate_text(text)
    assert any(i.field == "land_area" and i.severity == "error" for i in result.issues)


def test_duplicate_record_number_warns():
    text = _read("land_record.txt").replace(
        "Record Number: RL-2023-04512",
        "Record Number: RL-2023-04512\nRecord Number: RL-2023-04512",
    )
    result = validate_text(text)
    assert result.status in ("warning", "invalid")
    assert any(i.category == "duplicate" for i in result.issues)


def test_area_unit_conversion_no_false_conflict():
    # 2.35 ha == 5.81 acres should NOT be flagged as conflicting
    result = validate_text(_read("land_record.txt"))
    assert not any(i.category == "consistency" for i in result.issues)


def test_conflicting_area_warns():
    text = _read("land_record.txt").replace("2.35 hectares", "9.5 hectares")
    result = validate_text(text)
    assert any(i.category == "consistency" for i in result.issues)


def test_registration_before_document_date_warns():
    text = _read("land_record.txt").replace("16/08/2023", "14/08/2023")
    result = validate_text(text)
    assert any(i.category == "consistency" for i in result.issues)


def test_nil_marked_field_suspicious():
    text = _read("land_record.txt").replace("2.35 hectares (5.81 acres)", "N/A")
    result = validate_text(text)
    assert any(i.category == "suspicious" for i in result.issues)


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_name", "Sunita"),
        ("survey_number", "124/3"),
        ("village", "Kamalpur"),
    ],
)
def test_field_extraction_correct(field, value):
    result = validate_text(_read("land_record.txt"))
    assert value.lower() in result.fields.get(field, "").lower()


def test_owner_extraction_from_issues_doc():
    result = validate_text(_read("land_record_with_issues.txt"))
    assert "Rajesh Kumar" in result.fields.get("owner_name", "")