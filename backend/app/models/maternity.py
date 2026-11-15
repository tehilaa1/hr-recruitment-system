from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Adding a column:
#   1. add the field to MaternityLeaveBase *and* MaternityLeaveUpdate below
#   2. add one entry to MATERNITY_COLUMNS in frontend/src/constants/maternityColumns.js
#      (or to MATERNITY_STATUS_FIELDS for a row-level flag that has its own
#      action button and is not part of the add/edit form, like is_completed)
# Existing Firestore documents without the new field simply get its default.

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Baby's sex as shown in the UI and messages ("בן" = boy, "בת" = girl).
# Must match the `options` of baby_gender in frontend/src/constants/maternityColumns.js
# (enforced by tests/test_maternity_fields_sync.py).
BABY_GENDERS: tuple[str, ...] = ("בן", "בת")
BabyGender = Literal[BABY_GENDERS]  # type: ignore[valid-type]


def _blank_to_none(v):
    """The form sends "" for "not chosen"; store that as null."""
    return None if isinstance(v, str) and not v.strip() else v


class MaternityLeaveBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = ""
    company_email: str = ""
    birth_date: Optional[date] = None
    baby_gender: Optional[BabyGender] = None
    expected_return_date: Optional[date] = None
    gift_address: str = ""
    delivery_contact_name: str = ""
    delivery_contact_phone: str = ""
    attendance_updated: bool = False
    notes: str = ""
    # "סיום טיפול - יולדת חזרה": the employee is back; the record is kept but closed
    is_completed: bool = False

    _baby_gender_blank = field_validator("baby_gender", mode="before")(_blank_to_none)


class MaternityLeaveCreate(MaternityLeaveBase):
    pass


class MaternityLeaveUpdate(BaseModel):
    """Partial update; only fields that are sent are changed (null clears a date)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = None
    company_email: Optional[str] = None
    birth_date: Optional[date] = None
    baby_gender: Optional[BabyGender] = None
    expected_return_date: Optional[date] = None
    gift_address: Optional[str] = None
    delivery_contact_name: Optional[str] = None
    delivery_contact_phone: Optional[str] = None
    attendance_updated: Optional[bool] = None
    notes: Optional[str] = None
    is_completed: Optional[bool] = None

    _baby_gender_blank = field_validator("baby_gender", mode="before")(_blank_to_none)


class MaternityLeaveResponse(MaternityLeaveBase):
    # Relaxed for reading so older/partial documents never break the list
    name: str = ""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("baby_gender", mode="before")
    @classmethod
    def _unknown_gender_is_unset(cls, v):
        # Unknown values in old/hand-edited documents read as "not set" instead of failing the list
        return v if v in BABY_GENDERS else None


# Placeholders usable in message templates, e.g. "{name}".
# Must match TEMPLATE_PLACEHOLDERS in frontend/src/utils/maternityTemplates.js
# (enforced by tests/test_maternity_fields_sync.py).
TEMPLATE_PLACEHOLDERS: tuple[str, ...] = (
    "name",
    "phone",
    "company_email",
    "birth_date",
    "baby_gender",
    "baby_phrase",
    "baby_heart",
    "expected_return_date",
    "gift_address",
    "delivery_contact",
    "attendance_updated",
    "notes",
)

_PLACEHOLDER_RE = re.compile(r"\{([^{}\s]*)\}")
_MAX_TEMPLATE_LENGTH = 5000


class MaternityTemplates(BaseModel):
    """User-customized message templates. "" = use the built-in default text."""

    # הודעת עדכון ראשונית — short: she gave birth, HR will call for details
    initial_subject: str = ""
    initial_body: str = ""
    # הודעה עם הפרטים המלאים — every detail of the record
    full_subject: str = ""
    full_body: str = ""
    # Congratulations post for the Teams channel
    teams_announcement: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _check_template(cls, v):
        if v is None:
            return ""
        if not isinstance(v, str):
            return v
        if len(v) > _MAX_TEMPLATE_LENGTH:
            raise ValueError(f"תבנית ארוכה מדי (עד {_MAX_TEMPLATE_LENGTH} תווים)")
        unknown = sorted(set(_PLACEHOLDER_RE.findall(v)) - set(TEMPLATE_PLACEHOLDERS))
        if unknown:
            raise ValueError(
                "שדות לא מוכרים בתבנית: " + ", ".join("{" + u + "}" for u in unknown)
            )
        # Whitespace-only means "not customized"
        return v if v.strip() else ""


class MaternitySettings(BaseModel):
    """Module-wide settings, stored in Firestore at settings/maternity."""

    notify_recipients: List[str] = Field(default_factory=list)
    teams_channel_url: str = ""
    templates: MaternityTemplates = Field(default_factory=MaternityTemplates)

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
