"""Annual budget module: models, calculations and frontend status sync.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_budgets.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.budget import (  # noqa: E402
    DEFAULT_EVENT_STATUS,
    EVENT_STATUSES,
    AnnualBudgetCreate,
    BudgetEventCreate,
    BudgetEventResponse,
    BudgetEventUpdate,
    DEFAULT_EXPENSE_STATUS,
    EXPENSE_STATUSES,
    EventStatus,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseStatus,
    ExpenseUpdate,
)
from app.services.budget_service import (  # noqa: E402
    enrich_event,
    sort_events,
    sort_expenses,
    summarize_expenses,
    summarize_year,
)

FRONTEND_BUDGETS = BACKEND_DIR.parent / "frontend" / "src" / "constants" / "budgets.js"


def _frontend_block(name: str) -> str:
    source = FRONTEND_BUDGETS.read_text(encoding="utf-8")
    match = re.search(rf"export const {name}\s*=\s*([\[{{].*?[\]}}]);", source, re.S)
    assert match, f"{name} not found in {FRONTEND_BUDGETS}"
    return match.group(1)


def _raises(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("expected a validation error")


def test_statuses_in_sync_with_frontend():
    assert get_args(EventStatus) == EVENT_STATUSES
    assert re.findall(r"'([^']+)'", _frontend_block("EVENT_STATUSES")) == list(EVENT_STATUSES)
    styled = set(re.findall(r"'([^']+)'\s*:", _frontend_block("EVENT_STATUS_STYLES")))
    assert set(EVENT_STATUSES) <= styled, set(EVENT_STATUSES) - styled


def test_model_validation():
    assert AnnualBudgetCreate(year=2026, total_budget=120000.555).total_budget == 120000.56
    _raises(lambda: AnnualBudgetCreate(year=1999))
    _raises(lambda: AnnualBudgetCreate(year=2026, total_budget=-1))
    event = BudgetEventCreate(name="פסח", allocated_budget=5000, event_date="2026-04-01")
    assert event.status == DEFAULT_EVENT_STATUS
    assert event.model_dump(mode="json")["event_date"] == "2026-04-01"
    _raises(lambda: BudgetEventCreate(name=""))
    _raises(lambda: BudgetEventCreate(name="x", status="done"))
    assert BudgetEventUpdate(event_date=None).model_dump(exclude_unset=True) == {"event_date": None}


def test_summary_excludes_cancelled_and_computes_buffer():
    events = [
        {"name": "ראש השנה", "allocated_budget": 30000, "actual_spent": 32000.5, "status": "הסתיים"},
        {"name": "חנוכה", "allocated_budget": 15000, "actual_spent": 0, "status": "מתוכנן"},
        {"name": "פורים", "allocated_budget": 9000, "actual_spent": 1000, "status": "בוטל"},
    ]
    s = summarize_year({"year": 2026, "total_budget": 50000}, events)
    assert (s["allocated_total"], s["spent_total"], s["remaining"]) == (45000, 32000.5, 5000)
    assert s["events_count"] == 3
    over = summarize_year({"year": 2026, "total_budget": 40000}, events)
    assert over["remaining"] == -5000  # over-allocated shows as negative buffer


def test_event_variance_and_legacy_documents():
    e = enrich_event({"id": "e1", "name": "פסח", "allocated_budget": 5000, "actual_spent": 6200}, 2026)
    assert e["variance"] == -1200 and e["year"] == 2026 and e["status"] == DEFAULT_EVENT_STATUS
    legacy = enrich_event({"id": "e2"}, 2026)
    assert BudgetEventResponse(**legacy).variance == 0


def test_events_sorted_by_date_then_undated():
    events = [{"name": "ב", "event_date": None}, {"name": "א", "event_date": "2026-09-20"},
              {"name": "ג", "event_date": "2026-04-01"}]
    assert [e["name"] for e in sort_events(events)] == ["ג", "א", "ב"]


def test_expense_statuses_in_sync_with_frontend():
    assert get_args(ExpenseStatus) == EXPENSE_STATUSES == ("שולם", "ישולם בהעברה")
    assert re.findall(r"'([^']+)'", _frontend_block("EXPENSE_STATUSES")) == list(EXPENSE_STATUSES)
    styled = set(re.findall(r"'([^']+)'\s*:", _frontend_block("EXPENSE_STATUS_STYLES")))
    assert set(EXPENSE_STATUSES) <= styled, set(EXPENSE_STATUSES) - styled
    source = FRONTEND_BUDGETS.read_text(encoding="utf-8")
    assert f"DEFAULT_EXPENSE_STATUS = '{DEFAULT_EXPENSE_STATUS}'" in source


def test_expense_model_validation():
    item = ExpenseCreate(item_name="  סופגניות ", quantity=300, unit_price=4.5)
    assert item.item_name == "סופגניות"
    assert item.total_price == 1350 and item.status == DEFAULT_EXPENSE_STATUS
    # An explicit total wins over quantity × unit price (e.g. a bulk discount)
    assert ExpenseCreate(item_name="x", quantity=300, unit_price=4.5, total_price=1200).total_price == 1200
    assert ExpenseCreate(item_name="ספק הגברה", total_price=2500.555).total_price == 2500.56
    assert ExpenseCreate(item_name="x", quantity=2.5).quantity == 2.5
    _raises(lambda: ExpenseCreate(item_name="   "))
    _raises(lambda: ExpenseCreate(item_name="x", quantity=0))
    _raises(lambda: ExpenseCreate(item_name="x", total_price=-1))
    _raises(lambda: ExpenseCreate(item_name="x", status="paid"))
    assert ExpenseUpdate(unit_price=None).model_dump(exclude_unset=True) == {"unit_price": None}
    assert ExpenseResponse(id="legacy").total_price == 0


def test_expense_summary_and_event_count():
    expenses = [
        {"total_price": 1350, "status": "שולם"},
        {"total_price": 2500.5, "status": "ישולם בהעברה"},
        {"total_price": None},  # legacy/partial document: no amount, unknown status
    ]
    assert summarize_expenses(expenses) == {
        "count": 3, "total": 3850.5, "paid_total": 1350, "pending_total": 2500.5,
    }
    assert summarize_expenses([])["total"] == 0
    assert enrich_event({"id": "e", "expenses_count": 3}, 2026)["expenses_count"] == 3
    assert enrich_event({"id": "e"}, 2026)["expenses_count"] == 0


def test_expenses_sorted_in_insertion_order():
    from datetime import datetime, timezone

    t = lambda h: datetime(2026, 12, 1, h, tzinfo=timezone.utc)  # noqa: E731
    items = [{"item_name": "ב", "created_at": t(10)}, {"item_name": "ישן"}, {"item_name": "א", "created_at": t(9)}]
    assert [e["item_name"] for e in sort_expenses(items)] == ["ישן", "א", "ב"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
