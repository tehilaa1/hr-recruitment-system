from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# Adding a column:
#   1. add the field to MaternityLeaveBase *and* MaternityLeaveUpdate below
#   2. add one entry to MATERNITY_COLUMNS in frontend/src/constants/maternityColumns.js
#      (or to MATERNITY_STATUS_FIELDS for a row-level flag that has its own
#      action button and is not part of the add/edit form, like is_completed)
# Existing Firestore documents without the new field simply get its default.

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MaternityLeaveBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = ""
    company_email: str = ""
    birth_date: Optional[date] = None
    expected_return_date: Optional[date] = None
    gift_address: str = ""
    delivery_contact_name: str = ""
    delivery_contact_phone: str = ""
    attendance_updated: bool = False
    notes: str = ""
    # "סיום טיפול - יולדת חזרה": the employee is back; the record is kept but closed
    is_completed: bool = False


class MaternityLeaveCreate(MaternityLeaveBase):
    pass


class MaternityLeaveUpdate(BaseModel):
    """Partial update; only fields that are sent are changed (null clears a date)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = None
    company_email: Optional[str] = None
    birth_date: Optional[date] = None
    expected_return_date: Optional[date] = None
    gift_address: Optional[str] = None
    delivery_contact_name: Optional[str] = None
    delivery_contact_phone: Optional[str] = None
    attendance_updated: Optional[bool] = None
    notes: Optional[str] = None
    is_completed: Optional[bool] = None


class MaternityLeaveResponse(MaternityLeaveBase):
    # Relaxed for reading so older/partial documents never break the list
    name: str = ""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MaternitySettings(BaseModel):
    """Module-wide settings, stored in Firestore at settings/maternity."""

    notify_recipients: List[str] = Field(default_factory=list)
    teams_channel_url: str = ""

    @field_validator("notify_recipients")
    @classmethod
    def _validate_emails(cls, emails: List[str]) -> List[str]:
        cleaned, seen = [], set()
        for e in emails:
            e = (e or "").strip()
            if not e or e.lower() in seen:
                continue
            if not _EMAIL_RE.match(e):
                raise ValueError(f"כתובת מייל לא תקינה: {e}")
            seen.add(e.lower())
            cleaned.append(e)
        return cleaned

    @field_validator("teams_channel_url")
    @classmethod
    def _validate_teams_url(cls, url: str) -> str:
        url = (url or "").strip()
        if url and not url.startswith("https://"):
            raise ValueError("קישור הערוץ חייב להתחיל ב-https://")
        return url
