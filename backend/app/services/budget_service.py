"""Budget calculations (pure functions, no I/O)."""
from __future__ import annotations

from app.models.budget import DEFAULT_EVENT_STATUS, EXPENSE_STATUSES

# Cancelled events keep their history but don't consume the year's budget
_EXCLUDED_FROM_TOTALS = {"בוטל"}


def _money(value) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def enrich_event(event: dict, year: int) -> dict:
    allocated = _money(event.get("allocated_budget"))
    spent = _money(event.get("actual_spent"))
    return {
        **event,
        "year": year,
        "allocated_budget": allocated,
        "actual_spent": spent,
        "status": event.get("status") or DEFAULT_EVENT_STATUS,
        "variance": round(allocated - spent, 2),
        "expenses_count": int(event.get("expenses_count") or 0),
    }


def summarize_year(budget: dict, events: list[dict]) -> dict:
    """Year document + its events -> AnnualBudgetSummary fields."""
    year = int(budget["year"])
    counted = [e for e in events if (e.get("status") or "") not in _EXCLUDED_FROM_TOTALS]
    total = _money(budget.get("total_budget"))
    allocated = round(sum(_money(e.get("allocated_budget")) for e in counted), 2)
    spent = round(sum(_money(e.get("actual_spent")) for e in counted), 2)
    return {
        "year": year,
        "total_budget": total,
        "notes": budget.get("notes") or "",
        "allocated_total": allocated,
        "spent_total": spent,
        "remaining": round(total - allocated, 2),
        "events_count": len(events),
        "created_at": budget.get("created_at"),
        "updated_at": budget.get("updated_at"),
    }


def sort_events(events: list[dict]) -> list[dict]:
    """By date (undated last), then name."""
    return sorted(events, key=lambda e: (e.get("event_date") is None, str(e.get("event_date") or ""), e.get("name") or ""))


_PAID = EXPENSE_STATUSES[0]


def summarize_expenses(expenses: list[dict]) -> dict:
    """Totals of an event's expense items; anything not marked paid counts as pending."""
    total = paid = 0.0
    for e in expenses:
        amount = _money(e.get("total_price"))
        total += amount
        if e.get("status") == _PAID:
            paid += amount
    return {
        "count": len(expenses),
        "total": round(total, 2),
        "paid_total": round(paid, 2),
        "pending_total": round(total - paid, 2),
    }


def sort_expenses(expenses: list[dict]) -> list[dict]:
    """In the order they were added (documents without a timestamp first)."""
    return sorted(expenses, key=lambda e: (e.get("created_at") is not None, e.get("created_at") or 0))
