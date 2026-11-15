"""Budget calculations (pure functions, no I/O)."""
from __future__ import annotations

from app.models.budget import DEFAULT_EVENT_STATUS

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
