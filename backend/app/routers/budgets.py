"""Annual budget module: /api/budgets/{year} and /api/budgets/{year}/events/{event_id}.

Future itemized expenses per event belong under
/api/budgets/{year}/events/{event_id}/expenses (see app/models/budget.py).
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
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
)
from app.services.budget_service import enrich_event, sort_events, summarize_year
from app.services.firestore_service import FirestoreService

router = APIRouter(prefix="/api/budgets", tags=["Annual Budgets"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
Year = Annotated[int, Path(ge=MIN_YEAR, le=MAX_YEAR)]


# ------------------------------------------------------------------ #
# Years                                                                #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[AnnualBudgetSummary])
async def list_budget_years(db: DB):
    years = await asyncio.to_thread(db.list_budget_years)
    events = await asyncio.gather(
        *(asyncio.to_thread(db.list_budget_events, y["year"]) for y in years)
    )
    summaries = [summarize_year(y, ev) for y, ev in zip(years, events)]
    return sorted(summaries, key=lambda s: s["year"], reverse=True)


@router.post("", response_model=AnnualBudgetDetail, status_code=http_status.HTTP_201_CREATED)
async def create_budget_year(payload: AnnualBudgetCreate, db: DB):
    created = await asyncio.to_thread(
        db.create_budget_year, payload.year, payload.model_dump(exclude={"year"})
    )
    if created is None:
        raise HTTPException(http_status.HTTP_409_CONFLICT, f"כבר קיים תקציב לשנת {payload.year}")
    return {**summarize_year(created, []), "events": []}


@router.get("/{year}", response_model=AnnualBudgetDetail)
async def get_budget_year(year: Year, db: DB):
    budget, events = await asyncio.gather(
        asyncio.to_thread(db.get_budget_year, year),
        asyncio.to_thread(db.list_budget_events, year),
    )
    _assert_year(budget, year)
    return _detail(budget, events)


@router.patch("/{year}", response_model=AnnualBudgetDetail)
async def update_budget_year(year: Year, payload: AnnualBudgetUpdate, db: DB):
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    budget = await asyncio.to_thread(db.update_budget_year, year, update)
    _assert_year(budget, year)
    events = await asyncio.to_thread(db.list_budget_events, year)
    return _detail(budget, events)


@router.delete("/{year}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_budget_year(year: Year, db: DB):
    if not await asyncio.to_thread(db.delete_budget_year, year):
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"לא נמצא תקציב לשנת {year}")


# ------------------------------------------------------------------ #
# Events / holidays                                                    #
# ------------------------------------------------------------------ #


@router.post(
    "/{year}/events",
    response_model=BudgetEventResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_budget_event(year: Year, payload: BudgetEventCreate, db: DB):
    _assert_year(await asyncio.to_thread(db.get_budget_year, year), year)
    # mode="json" stores dates as "YYYY-MM-DD" strings (Firestore has no date-only type)
    saved = await asyncio.to_thread(db.create_budget_event, year, payload.model_dump(mode="json"))
    return enrich_event(saved, year)


@router.patch("/{year}/events/{event_id}", response_model=BudgetEventResponse)
async def update_budget_event(year: Year, event_id: str, payload: BudgetEventUpdate, db: DB):
    update = payload.model_dump(mode="json", exclude_unset=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    for field in ("name", "allocated_budget", "actual_spent", "status", "notes"):
        if field in update and update[field] is None:
            raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field} cannot be null")
    saved = await asyncio.to_thread(db.update_budget_event, year, event_id, update)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "האירוע לא נמצא")
    return enrich_event(saved, year)


@router.delete("/{year}/events/{event_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_budget_event(year: Year, event_id: str, db: DB):
    if not await asyncio.to_thread(db.delete_budget_event, year, event_id):
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "האירוע לא נמצא")


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
