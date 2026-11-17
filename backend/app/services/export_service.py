"""Styled RTL .xlsx exports (candidates, maternity leaves, holiday expenses)."""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Literal, Optional
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

CellKind = Literal["auto", "text", "number", "money", "date", "bool"]

_MONEY_FORMAT = '#,##0.00 "₪"'
_DATE_FORMAT = "DD/MM/YYYY"


@dataclass(frozen=True)
class Column:
    field: str
    header: str
    width: int = 16
    kind: CellKind = "auto"


# ------------------------------------------------------------------ #
# Column sets                                                          #
# ------------------------------------------------------------------ #

CANDIDATE_COLUMNS: tuple[Column, ...] = (
    Column("full_name", "שם פרטי", 16),
    Column("family_name", "שם משפחה", 16),
    Column("phone", "טלפון", 16, "text"),
    Column("email", "אימייל", 30),
    Column("address", "כתובת", 28),
    Column("profession", "מקצוע", 22),
    Column("years_of_experience", "שנות ניסיון", 12, "number"),
    Column("recruitment_status", "סטטוס גיוס", 16),
)

# Privacy: an explicit allow-list, so fields added to the model later are never
# exported by accident. Gift address and delivery contact details are personal
# data that must stay inside the app (see tests/test_exports.py).
MATERNITY_EXPORT_COLUMNS: tuple[Column, ...] = (
    Column("name", "שם העובדת", 22),
    Column("phone", "טלפון", 16, "text"),
    Column("company_email", "מייל בחברה", 30, "text"),
    Column("birth_date", "תאריך לידה", 14, "date"),
    Column("expected_return_date", "תאריך חזרה לעבודה", 18, "date"),
    Column("attendance_updated", "עודכן בנוכחות", 14, "bool"),
    Column("notes", "הערות", 40, "text"),
)
MATERNITY_EXCLUDED_FIELDS = frozenset({"gift_address", "delivery_contact_name", "delivery_contact_phone"})

EXPENSE_COLUMNS: tuple[Column, ...] = (
    Column("item_name", "שם המוצר / ספק", 28, "text"),
    Column("quantity", "כמות", 10, "number"),
    Column("unit_price", "מחיר ליחידה", 14, "money"),
    Column("total_price", "סכום כולל", 15, "money"),
    Column("status", "סטטוס תשלום", 16, "text"),
    Column("invoice_reference", "אסמכתת חשבונית", 26, "text"),
    Column("notes", "הערות", 36, "text"),
)


# ------------------------------------------------------------------ #
# Workbook builder                                                     #
# ------------------------------------------------------------------ #

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="2563EB")
_TITLE_FONT = Font(bold=True, size=14)
_TOTAL_FONT = Font(bold=True)
_TOTAL_FILL = PatternFill("solid", fgColor="F3F4F6")
_TOTAL_BORDER = Border(top=Side(style="medium", color="9CA3AF"))
_RIGHT = Alignment(horizontal="right", vertical="center")
_WRAP = Alignment(horizontal="right", vertical="top", wrap_text=True)


def build_xlsx(
    rows: Iterable[dict],
    columns: Iterable[Column],
    sheet_title: str,
    *,
    title: Optional[str] = None,
    summary: Optional[list[tuple[str, dict]]] = None,
) -> bytes:
    """One RTL sheet: optional title line, styled header, data rows, summary rows.

    ``summary`` rows are (label, {field: value}); the label goes in the first
    column and each value under its field's column, formatted by its kind.
    """
    columns = tuple(columns)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31] or "Sheet"  # Excel sheet-name limit
    ws.sheet_view.rightToLeft = True

    if title:
        ws.append([title])
        ws.cell(row=1, column=1).font = _TITLE_FONT
        ws.append([])

    ws.append([c.header for c in columns])
    header_row = ws.max_row
    for cell in ws[header_row]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _RIGHT

    for row in rows:
        ws.append([_cell_value(c, (row or {}).get(c.field)) for c in columns])
        _format_row(ws, ws.max_row, columns)

    for i, (label, values) in enumerate(summary or []):
        ws.append([label] + [""] * (len(columns) - 1))
        r = ws.max_row
        for idx, col in enumerate(columns, start=1):
            if col.field in values:
                ws.cell(row=r, column=idx).value = _cell_value(col, values[col.field])
        _format_row(ws, r, columns)
        for cell in ws[r]:
            cell.font = _TOTAL_FONT
            cell.fill = _TOTAL_FILL
            if i == 0:
                cell.border = _TOTAL_BORDER

    for idx, col in enumerate(columns, start=1):
        ws.column_dimensions[ws.cell(row=header_row, column=idx).column_letter].width = col.width

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def generate_xlsx(candidates: list[dict], sheet_title: str = "מועמדים") -> bytes:
    return build_xlsx(candidates, CANDIDATE_COLUMNS, sheet_title or "מועמדים")


def generate_maternity_xlsx(records: list[dict]) -> bytes:
    return build_xlsx(records, MATERNITY_EXPORT_COLUMNS, "חופשות לידה")


def generate_expenses_xlsx(event: dict, expenses: list[dict], summary: dict) -> bytes:
    name = str(event.get("name") or "אירוע")
    year = event.get("year")
    rows = [
        ("סה״כ", {"total_price": summary["total"]}),
        ("שולם", {"total_price": summary["paid_total"]}),
        ("ישולם בהעברה", {"total_price": summary["pending_total"]}),
        ("תקציב מוקצה", {"total_price": event.get("allocated_budget") or 0}),
        ("יתרה בתקציב", {"total_price": round((event.get("allocated_budget") or 0) - summary["total"], 2)}),
    ]
    return build_xlsx(
        expenses,
        EXPENSE_COLUMNS,
        "פירוט הוצאות",
        title=f"{name} {year} – פירוט הוצאות" if year else f"{name} – פירוט הוצאות",
        summary=rows,
    )


# ------------------------------------------------------------------ #
# HTTP helper                                                          #
# ------------------------------------------------------------------ #

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def content_disposition(prefix: str, label: str = "") -> str:
    """Content-Disposition for "<prefix>_<label>.xlsx" that survives Hebrew labels.

    HTTP headers must be latin-1, so the plain ``filename`` gets an ASCII-only
    fallback while ``filename*`` (RFC 5987) carries the real UTF-8 name.
    """
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)[:50].strip("_")
    utf8_name = f"{prefix}_{safe}.xlsx" if safe else f"{prefix}.xlsx"
    ascii_label = "".join(c for c in safe if c.isascii()).strip("_")
    ascii_name = f"{prefix}_{ascii_label}.xlsx" if ascii_label else f"{prefix}.xlsx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(utf8_name)}"


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _format_row(ws, row: int, columns: tuple[Column, ...]) -> None:
    for idx, col in enumerate(columns, start=1):
        cell = ws.cell(row=row, column=idx)
        if col.kind == "money" and isinstance(cell.value, (int, float)):
            cell.number_format = _MONEY_FORMAT
        elif col.kind == "date" and isinstance(cell.value, date):
            cell.number_format = _DATE_FORMAT
        cell.alignment = _WRAP if col.width >= 30 else _RIGHT


def _cell_value(col: Column, value: Any) -> Any:
    """Coerce a raw Firestore value into something openpyxl can always write.

    Missing fields become "", numbers stay numeric, dates become real Excel
    dates, and anything else (lists, dicts, tz-aware timestamps, ...) is text.
    """
    if col.kind == "bool":
        return "כן" if value is True else "לא"
    if value is None or value == "":
        return ""
    if col.kind == "text":
        # Phone numbers stay text so Excel doesn't drop the leading 0
        return str(value)
    if col.kind in ("number", "money"):
        try:
            n = float(value)
        except (TypeError, ValueError):
            return str(value)
        return int(n) if col.kind == "number" and n.is_integer() else n
    if col.kind == "date":
        return _as_date(value)
    if isinstance(value, bool):
        return "כן" if value else "לא"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


def _as_date(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return str(value)
