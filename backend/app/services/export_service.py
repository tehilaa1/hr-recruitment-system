from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

_COLUMNS: list[tuple[str, str, int]] = [
    # (field, Hebrew header, column width)
    ("full_name", "שם פרטי", 16),
    ("family_name", "שם משפחה", 16),
    ("phone", "טלפון", 16),
    ("email", "אימייל", 30),
    ("address", "כתובת", 28),
    ("profession", "מקצוע", 22),
    ("years_of_experience", "שנות ניסיון", 12),
    ("recruitment_status", "סטטוס גיוס", 16),
]


def generate_xlsx(candidates: list[dict], sheet_title: str = "מועמדים") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31] or "מועמדים"  # Excel sheet-name limit
    ws.sheet_view.rightToLeft = True

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")
    right = Alignment(horizontal="right", vertical="center")

    ws.append([label for _, label, _ in _COLUMNS])
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = right

    for candidate in candidates:
        ws.append([_cell_value(field, (candidate or {}).get(field)) for field, _, _ in _COLUMNS])

    for idx, (_, _, width) in enumerate(_COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width

    ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _cell_value(field: str, value: Any) -> str | int | float:
    """Coerce a raw Firestore value into something openpyxl can always write.

    Missing fields become "", numbers stay numeric, and anything else
    (lists, dicts, tz-aware timestamps, ...) is rendered as text.
    """
    if value is None:
        return ""
    if field == "phone":
        # Keep as text so Excel doesn't drop the leading 0
        return str(value)
    if isinstance(value, bool):
        return "כן" if value else "לא"
    if isinstance(value, (int, float)):
        return value
    if field == "years_of_experience":
        try:
            return float(value) if "." in str(value) else int(value)
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)
