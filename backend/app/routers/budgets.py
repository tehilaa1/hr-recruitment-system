"""Annual budget module.

    /api/budgets/{year}
    /api/budgets/{year}/events/{event_id}
    /api/budgets/{year}/events/{event_id}/expenses/{expense_id}
    /api/budgets/{year}/events/{event_id}/expenses/{expense_id}/invoice   (PDF/PNG/JPG file)
    /api/budgets/{year}/events/{event_id}/export-excel
"""
from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Response, UploadFile
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.budget import (
    MAX_YEAR,
    MIN_YEAR,
    AnnualBudgetCreate,
    AnnualBudgetDetail,
    AnnualBudgetSummary,
    AnnualBudgetUpdate,
    BudgetEventCreate,
    BudgetEventResponse,
    BudgetEventUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    INVOICE_MAX_BYTES,
)
from app.services.budget_service import (
    enrich_event,
    sort_events,
    sort_expenses,
    summarize_expenses,
    summarize_year,
)
from app.services.export_service import XLSX_MEDIA_TYPE, content_disposition, generate_expenses_xlsx
from app.security import AuthUser
from app.services.demo_limits import max_upload_bytes
from app.services.firestore_service import FirestoreService
from app.services.invoice_service import detect_content_type, inline_disposition, safe_file_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/budgets", tags=["Annual Budgets"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
Year = Annotated[int, Path(ge=MIN_YEAR, le=MAX_YEAR)]


# ------------------------------------------------------------------ #
# Years                                                                #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[AnnualBudgetSummary])
async def list_budget_years(user: AuthUser, db: DB):
    years = await asyncio.to_thread(db.list_budget_years, user.tenant_id)
    events = await asyncio.gather(
        *(asyncio.to_thread(db.list_budget_events, user.tenant_id, y["year"]) for y in years)
    )
    summaries = [summarize_year(y, ev) for y, ev in zip(years, events)]
    return sorted(summaries, key=lambda s: s["year"], reverse=True)


@router.post("", response_model=AnnualBudgetDetail, status_code=http_status.HTTP_201_CREATED)
async def create_budget_year(payload: AnnualBudgetCreate, user: AuthUser, db: DB):
    created = await asyncio.to_thread(
        db.create_budget_year, user.tenant_id, payload.year, payload.model_dump(exclude={"year"})
    )
    if created is None:
        raise HTTPException(http_status.HTTP_409_CONFLICT, f"כבר קיים תקציב לשנת {payload.year}")
    return {**summarize_year(created, []), "events": []}


@router.get("/{year}", response_model=AnnualBudgetDetail)
async def get_budget_year(year: Year, user: AuthUser, db: DB):
    budget, events = await asyncio.gather(
        asyncio.to_thread(db.get_budget_year, user.tenant_id, year),
        asyncio.to_thread(db.list_budget_events, user.tenant_id, year),
    )
    _assert_year(budget, year)
    return _detail(budget, events)


@router.patch("/{year}", response_model=AnnualBudgetDetail)
async def update_budget_year(year: Year, payload: AnnualBudgetUpdate, user: AuthUser, db: DB):
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    budget = await asyncio.to_thread(db.update_budget_year, user.tenant_id, year, update)
    _assert_year(budget, year)
    events = await asyncio.to_thread(db.list_budget_events, user.tenant_id, year)
    return _detail(budget, events)


@router.delete("/{year}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_budget_year(year: Year, user: AuthUser, db: DB):
    if not await asyncio.to_thread(db.delete_budget_year, user.tenant_id, year):
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"לא נמצא תקציב לשנת {year}")


# ------------------------------------------------------------------ #
# Events / holidays                                                    #
# ------------------------------------------------------------------ #


@router.post(
    "/{year}/events",
    response_model=BudgetEventResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_budget_event(year: Year, payload: BudgetEventCreate, user: AuthUser, db: DB):
    _assert_year(await asyncio.to_thread(db.get_budget_year, user.tenant_id, year), year)
    # mode="json" stores dates as "YYYY-MM-DD" strings (Firestore has no date-only type)
    saved = await asyncio.to_thread(db.create_budget_event, user.tenant_id, year, payload.model_dump(mode="json"))
    return enrich_event(saved, year)


@router.patch("/{year}/events/{event_id}", response_model=BudgetEventResponse)
async def update_budget_event(
    year: Year, event_id: str, payload: BudgetEventUpdate, user: AuthUser, db: DB
):
    update = payload.model_dump(mode="json", exclude_unset=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    _reject_nulls(update, ("name", "allocated_budget", "actual_spent", "status", "notes"))
    if "actual_spent" in update:
        # With itemized expenses, actual_spent is derived from them and can't be set by hand
        event = await asyncio.to_thread(db.get_budget_event, user.tenant_id, year, event_id)
        if event and int(event.get("expenses_count") or 0) > 0:
            update.pop("actual_spent")
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    saved = await asyncio.to_thread(db.update_budget_event, user.tenant_id, year, event_id, update)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "האירוע לא נמצא")
    return enrich_event(saved, year)


@router.delete("/{year}/events/{event_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_budget_event(year: Year, event_id: str, user: AuthUser, db: DB):
    if not await asyncio.to_thread(db.delete_budget_event, user.tenant_id, year, event_id):
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "האירוע לא נמצא")


# ------------------------------------------------------------------ #
# Itemized expenses under an event                                     #
# ------------------------------------------------------------------ #

_EXPENSE_NOT_FOUND = "פריט ההוצאה לא נמצא"


@router.get("/{year}/events/{event_id}/expenses", response_model=list[ExpenseResponse])
async def list_event_expenses(year: Year, event_id: str, user: AuthUser, db: DB):
    event, expenses = await asyncio.gather(
        asyncio.to_thread(db.get_budget_event, user.tenant_id, year, event_id),
        asyncio.to_thread(db.list_event_expenses, user.tenant_id, year, event_id),
    )
    _assert_event(event)
    return sort_expenses(expenses)


@router.post(
    "/{year}/events/{event_id}/expenses",
    response_model=ExpenseResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_event_expense(
    year: Year, event_id: str, payload: ExpenseCreate, user: AuthUser, db: DB
):
    saved = await asyncio.to_thread(db.create_event_expense, user.tenant_id, year, event_id, payload.model_dump())
    _assert_event(saved)
    return saved


@router.patch("/{year}/events/{event_id}/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_event_expense(
    year: Year, event_id: str, expense_id: str, payload: ExpenseUpdate, user: AuthUser, db: DB
):
    update = payload.model_dump(exclude_unset=True)
    _reject_nulls(update, ("item_name", "quantity", "total_price", "status", "notes", "invoice_reference"))
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    saved = await asyncio.to_thread(db.update_event_expense, user.tenant_id, year, event_id, expense_id, update)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, _EXPENSE_NOT_FOUND)
    return saved


@router.delete(
    "/{year}/events/{event_id}/expenses/{expense_id}", status_code=http_status.HTTP_204_NO_CONTENT
)
async def delete_event_expense(year: Year, event_id: str, expense_id: str, user: AuthUser, db: DB):
    if not await asyncio.to_thread(db.delete_event_expense, user.tenant_id, year, event_id, expense_id):
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, _EXPENSE_NOT_FOUND)


_INVOICE_PATH = "/{year}/events/{event_id}/expenses/{expense_id}/invoice"
_NO_INVOICE = "לא צורף קובץ חשבונית"


@router.put(_INVOICE_PATH, response_model=ExpenseResponse)
async def upload_expense_invoice(
    year: Year, event_id: str, expense_id: str, user: AuthUser, db: DB, file: UploadFile = File(...)
):
    """Attach (or replace) the expense's invoice: PDF, PNG or JPG up to 5 MB."""
    max_bytes = max_upload_bytes(user, INVOICE_MAX_BYTES)
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"הקובץ גדול מדי (עד {max_bytes // (1024 * 1024)}MB)",
        )
    if not data:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "הקובץ ריק")
    content_type = detect_content_type(data)
    if content_type is None:
        raise HTTPException(
            http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "סוג קובץ לא נתמך – PDF, PNG או JPG בלבד"
        )
    meta = {
        "file_name": safe_file_name(file.filename, content_type),
        "content_type": content_type,
        "size": len(data),
    }
    saved = await asyncio.to_thread(db.set_expense_invoice, user.tenant_id, year, event_id, expense_id, meta, data)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, _EXPENSE_NOT_FOUND)
    return saved


@router.get(_INVOICE_PATH)
async def get_expense_invoice(year: Year, event_id: str, expense_id: str, user: AuthUser, db: DB):
    found = await asyncio.to_thread(db.get_expense_invoice, user.tenant_id, year, event_id, expense_id)
    if found is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, _NO_INVOICE)
    meta, data = found
    return Response(
        content=data,
        media_type=meta["content_type"],
        headers={
            "Content-Disposition": inline_disposition(meta.get("file_name") or "invoice"),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(_INVOICE_PATH, response_model=ExpenseResponse)
async def delete_expense_invoice(
    year: Year, event_id: str, expense_id: str, user: AuthUser, db: DB
):
    saved = await asyncio.to_thread(db.delete_expense_invoice, user.tenant_id, year, event_id, expense_id)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, _EXPENSE_NOT_FOUND)
    return saved


@router.get("/{year}/events/{event_id}/export-excel")
async def export_event_expenses_excel(year: Year, event_id: str, user: AuthUser, db: DB):
    event, expenses = await asyncio.gather(
        asyncio.to_thread(db.get_budget_event, user.tenant_id, year, event_id),
        asyncio.to_thread(db.list_event_expenses, user.tenant_id, year, event_id),
    )
    _assert_event(event)
    event = enrich_event(event, year)
    try:
        expenses = sort_expenses(expenses)
        xlsx_bytes = await asyncio.to_thread(
            generate_expenses_xlsx, event, expenses, summarize_expenses(expenses)
        )
    except Exception:
        logger.exception("Expenses Excel export failed for %s/%s", year, event_id)
        raise HTTPException(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate Excel export"
        )
    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition("expenses", f"{event['name']}_{year}")},
    )


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _detail(budget: dict, events: list[dict]) -> dict:
    return {
        **summarize_year(budget, events),
        "events": [enrich_event(e, budget["year"]) for e in sort_events(events)],
    }


def _assert_year(budget, year: int) -> None:
    if budget is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"לא נמצא תקציב לשנת {year}")


def _assert_event(event) -> None:
    if event is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "האירוע לא נמצא")


def _reject_nulls(update: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        if field in update and update[field] is None:
            raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field} cannot be null")
