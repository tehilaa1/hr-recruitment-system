"""Annual budget module: a budget per year, and holidays/events under each year.

Firestore layout (hierarchical):
    annual_budgets/{year}                    total_budget, notes, timestamps
    annual_budgets/{year}/events/{event_id}  name, allocated_budget, actual_spent,
                                             event_date, status, notes,
                                             expenses_count, timestamps
    annual_budgets/{year}/events/{event_id}/expenses/{expense_id}
                                             item_name, quantity, unit_price,
                                             total_price, status, notes,
                                             invoice_reference, timestamps

Once an event has itemized expenses, its actual_spent is the sum of their
total_price (kept in sync by FirestoreService on every expense write); events
without expenses keep a manually entered actual_spent.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

# Must stay identical, in the same order, to EVENT_STATUSES in
# frontend/src/constants/budgets.js (enforced by tests/test_budgets.py).
EVENT_STATUSES: tuple[str, ...] = ("מתוכנן", "בביצוע", "הסתיים", "בוטל")
DEFAULT_EVENT_STATUS = EVENT_STATUSES[0]
EventStatus = Literal[EVENT_STATUSES]  # type: ignore[valid-type]

MIN_YEAR, MAX_YEAR = 2000, 2100


def round_money(value: float) -> float:
    """Round to agorot, half-up on the decimal value (120000.555 -> 120000.56)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Shekels, never negative, stored with agorot precision
Money = Annotated[float, Field(ge=0, le=1_000_000_000), AfterValidator(round_money)]

# Item count; fractions allowed (e.g. 2.5 kg)
Quantity = Annotated[float, Field(gt=0, le=1_000_000), AfterValidator(lambda v: round(v, 3))]

# Must stay identical, in the same order, to EXPENSE_STATUSES in
# frontend/src/constants/budgets.js (enforced by tests/test_budgets.py).
EXPENSE_STATUSES: tuple[str, ...] = ("שולם", "ישולם בהעברה")
DEFAULT_EXPENSE_STATUS = EXPENSE_STATUSES[1]
ExpenseStatus = Literal[EXPENSE_STATUSES]  # type: ignore[valid-type]


# ------------------------------------------------------------------ #
# Annual budget                                                        #
# ------------------------------------------------------------------ #


class AnnualBudgetCreate(BaseModel):
    year: int = Field(..., ge=MIN_YEAR, le=MAX_YEAR)
    total_budget: Money = 0
    notes: str = Field("", max_length=2000)


class AnnualBudgetUpdate(BaseModel):
    total_budget: Optional[Money] = None
    notes: Optional[str] = Field(None, max_length=2000)


class AnnualBudgetSummary(BaseModel):
    year: int
    total_budget: float = 0
    notes: str = ""
    # Derived from the year's events (cancelled events are excluded)
    allocated_total: float = 0
    spent_total: float = 0
    remaining: float = 0  # total_budget - allocated_total (the unallocated buffer)
    events_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ------------------------------------------------------------------ #
# Events / holidays under a year                                       #
# ------------------------------------------------------------------ #


class BudgetEventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    allocated_budget: Money = 0
    actual_spent: Money = 0
    event_date: Optional[date] = None
    status: EventStatus = DEFAULT_EVENT_STATUS
    notes: str = Field("", max_length=2000)


class BudgetEventCreate(BudgetEventBase):
    pass


class BudgetEventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    allocated_budget: Optional[Money] = None
    actual_spent: Optional[Money] = None
    event_date: Optional[date] = None  # null clears the date
    status: Optional[EventStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)


class BudgetEventResponse(BudgetEventBase):
    # Relaxed for reading so older/partial documents never break the list
    name: str = ""
    status: str = DEFAULT_EVENT_STATUS
    id: str
    year: int
    variance: float = 0  # allocated_budget - actual_spent (negative = over budget)
    expenses_count: int = 0  # > 0 means actual_spent is derived from the expense items
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AnnualBudgetDetail(AnnualBudgetSummary):
    events: list[BudgetEventResponse] = []


# ------------------------------------------------------------------ #
# Itemized expenses under an event                                     #
# ------------------------------------------------------------------ #


class ExpenseBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_name: str = Field(..., min_length=1, max_length=200)  # product or supplier
    quantity: Quantity = 1
    unit_price: Optional[Money] = None
    total_price: Money = 0
    status: ExpenseStatus = DEFAULT_EXPENSE_STATUS
    notes: str = Field("", max_length=2000)
    # Invoice number, file name or link, added once the expense is paid
    invoice_reference: str = Field("", max_length=500)


class ExpenseCreate(ExpenseBase):
    @model_validator(mode="after")
    def _total_from_unit_price(self):
        if "total_price" not in self.model_fields_set and self.unit_price is not None:
            self.total_price = round_money(self.unit_price * self.quantity)
        return self


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_name: Optional[str] = Field(None, min_length=1, max_length=200)
    quantity: Optional[Quantity] = None
    unit_price: Optional[Money] = None  # null clears it
    total_price: Optional[Money] = None
    status: Optional[ExpenseStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)
    invoice_reference: Optional[str] = Field(None, max_length=500)


class ExpenseResponse(BaseModel):
    # Relaxed for reading so older/partial documents never break the list
    id: str
    item_name: str = ""
    quantity: float = 1
    unit_price: Optional[float] = None
    total_price: float = 0
    status: str = DEFAULT_EXPENSE_STATUS
    notes: str = ""
    invoice_reference: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
