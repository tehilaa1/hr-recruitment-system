"""Excel exports: maternity privacy filter, holiday expenses, candidates.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_exports.py)
"""
from __future__ import annotations

import io
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from openpyxl import load_workbook  # noqa: E402

from app.models.maternity import MaternityLeaveBase  # noqa: E402
from app.services.budget_service import summarize_expenses  # noqa: E402
from app.services.export_service import (  # noqa: E402
    MATERNITY_EXCLUDED_FIELDS,
    MATERNITY_EXPORT_COLUMNS,
    content_disposition,
    generate_expenses_xlsx,
    generate_maternity_xlsx,
    generate_xlsx,
)

# Fictional sample data
_MATERNITY_RECORD = {
    "id": "m1",
    "name": "דנה לוי",
    "phone": "050-1234567",
    "company_email": "dana@example.com",
    "birth_date": "2026-03-01",
    "baby_gender": "בת",
    "expected_return_date": "2026-06-14",
    "gift_address": "רחוב הדוגמה 1, עיר",
    "delivery_contact_name": "יוסי לוי",
    "delivery_contact_phone": "052-7654321",
    "attendance_updated": True,
    "notes": "הערה",
    "is_completed": False,
}


def _sheet(xlsx: bytes):
    return load_workbook(io.BytesIO(xlsx)).active


def _all_values(ws) -> list:
    return [c.value for row in ws.iter_rows() for c in row if c.value not in (None, "")]


def test_maternity_export_excludes_private_fields():
    ws = _sheet(generate_maternity_xlsx([_MATERNITY_RECORD]))
    headers = [c.value for c in ws[1]]
    # Column A is the first one; the sheet is right-to-left, so A is the right-most
    assert headers == ["שם העובדת", "טלפון", "מייל חברה", "תאריך לידה", "תאריך חזרה לעבודה", "עודכן בנוכחות", "הערות"]
    assert [c.column_letter for c in ws[1]] == list("ABCDEFG")
    values = [str(v) for v in _all_values(ws)]
    for field in MATERNITY_EXCLUDED_FIELDS:
        assert _MATERNITY_RECORD[field] not in values, field
    assert not any("כתובת" in h or "איש קשר" in h for h in headers)


def test_maternity_export_columns_are_real_fields_and_values_are_typed():
    model_fields = set(MaternityLeaveBase.model_fields)
    exported = {c.field for c in MATERNITY_EXPORT_COLUMNS}
    assert exported <= model_fields, exported - model_fields
    assert not exported & MATERNITY_EXCLUDED_FIELDS
    assert MATERNITY_EXCLUDED_FIELDS <= model_fields  # a rename must update the filter

    ws = _sheet(generate_maternity_xlsx([_MATERNITY_RECORD, {"id": "legacy", "name": "x"}]))
    assert ws.sheet_view.rightToLeft is True and ws.freeze_panes == "A2"
    row = [c.value for c in ws[2]]
    assert row[1] == "050-1234567"  # text: leading 0 kept
    assert row[3].date() == date(2026, 3, 1) and row[4].date() == date(2026, 6, 14)
    for col in (4, 5):  # native Excel dates with a locale-safe format code
        assert ws.cell(2, col).is_date and ws.cell(2, col).number_format == "dd/mm/yyyy"
    assert row[5] == "כן"
    legacy = [c.value for c in ws[3]]
    assert legacy[5] == "לא" and legacy[3] in (None, "")


def test_expenses_export_has_title_items_and_totals():
    event = {"name": "חנוכה", "year": 2026, "allocated_budget": 5000}
    expenses = [
        {"item_name": "סופגניות", "quantity": 300, "unit_price": 4.5, "total_price": 1350,
         "status": "שולם", "invoice_reference": "INV-1001", "notes": ""},
        {"item_name": "ספק הגברה", "quantity": 1, "unit_price": None, "total_price": 4000,
         "status": "ישולם בהעברה", "invoice_reference": "", "notes": "מקדמה"},
    ]
    ws = _sheet(generate_expenses_xlsx(event, expenses, summarize_expenses(expenses)))
    assert ws.sheet_view.rightToLeft is True
    assert ws["A1"].value == "חנוכה 2026 – פירוט הוצאות"
    assert [c.value for c in ws[3]][:4] == ["שם המוצר / ספק", "כמות", "מחיר ליחידה", "סכום כולל"]
    assert ws.freeze_panes == "A4"
    assert [c.value for c in ws[4]][:6] == ["סופגניות", 300, 4.5, 1350, "שולם", "INV-1001"]
    assert ws.cell(4, 4).number_format.startswith("#,##0.00")
    totals = {ws.cell(r, 1).value: ws.cell(r, 4).value for r in range(6, ws.max_row + 1)}
    assert totals == {"סה״כ": 5350, "שולם": 1350, "ישולם בהעברה": 4000, "תקציב מוקצה": 5000, "יתרה בתקציב": -350}


def test_candidates_export_unchanged():
    ws = _sheet(generate_xlsx([{"full_name": "דנה", "phone": "0501234567", "years_of_experience": "5"}]))
    assert [c.value for c in ws[1]][:3] == ["שם פרטי", "שם משפחה", "טלפון"]
    row = [c.value for c in ws[2]]
    assert row[2] == "0501234567" and row[6] == 5


def test_content_disposition_hebrew_and_ascii():
    header = content_disposition("expenses", "חנוכה_2026")
    assert 'filename="expenses_2026.xlsx"' in header
    assert "filename*=UTF-8''expenses_%D7%97" in header
    assert 'filename="maternity_leaves_2026-11-17.xlsx"' in content_disposition("maternity_leaves", "2026-11-17")
    assert 'filename="candidates.xlsx"' in content_disposition("candidates", "מנהלת")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
