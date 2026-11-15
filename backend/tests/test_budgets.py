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
    EventStatus,
)
from app.services.budget_service import enrich_event, sort_events, summarize_year  # noqa: E402

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


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
