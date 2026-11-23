from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.password_policy import (
    PASSWORD_MAX_LENGTH,
    password_problems,
    passwords_match_problems,
)

# Must stay identical to ROLES in frontend/src/constants/roles.js
# (enforced by tests/test_roles_sync.py).
#   admin  – full access + user management
#   editor – full access to jobs, candidates and maternity data
VALID_ROLES: tuple[str, ...] = ("admin", "editor")

Role = Literal[VALID_ROLES]  # type: ignore[valid-type]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_user_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_phone_e164(value: str) -> str:
    """Phone for SMS in E.164 ("+972501234567"); "" stays "" (no phone).

    Israeli local numbers ("050-123-4567") get the +972 prefix. Raises ValueError
    for anything that can't be a valid number.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        e164 = "+" + digits
    elif digits.startswith("00"):
        e164 = "+" + digits[2:]
    elif digits.startswith("972"):
        e164 = "+" + digits
    elif digits.startswith("0"):
        e164 = "+972" + digits[1:]
    else:
        raise ValueError("מספר טלפון לא תקין")
    if not 9 <= len(e164) - 1 <= 15:
        raise ValueError("מספר טלפון לא תקין")
    return e164


def mask_phone(phone: str) -> str:
    """"+972501234567" -> "•••••••4567" (only the last 4 digits are shown)."""
    digits = re.sub(r"\D", "", phone or "")
    return "•" * max(0, len(digits) - 4) + digits[-4:] if digits else ""


class _PhoneMixin(BaseModel):
    @field_validator("phone", mode="before", check_fields=False)
    @classmethod
    def _valid_phone(cls, v):
        return v if v is None else normalize_phone_e164(v)


class UserCreate(_PhoneMixin):
    email: str
    display_name: str = Field("", max_length=100)
    role: Role = "editor"
    # Mobile number for SMS verification codes (password reset)
    phone: str = ""

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = normalize_user_email(v)
        if not _EMAIL_RE.match(v):
            raise ValueError("כתובת מייל לא תקינה")
        return v


class UserUpdate(_PhoneMixin):
    display_name: Optional[str] = Field(None, max_length=100)
    role: Optional[Role] = None
    phone: Optional[str] = None  # "" removes the phone


class UserResponse(BaseModel):
    email: str
    display_name: str = ""
    role: Role
    phone: str = ""
    uid: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    tenant_id: Optional[str] = None


class MeResponse(UserResponse):
    """The signed-in user, plus the flags the UI needs."""
    is_super_admin: bool = False
    # Signed in to the shared public demo workspace (the UI shows a sandbox banner)
    is_demo: bool = False


class UserCreateResult(BaseModel):
    user: UserResponse
    # False when a Firebase Auth account with this email already existed
    created_account: bool


# ------------------------------------------------------------------ #
# Password reset with SMS verification                                 #
# ------------------------------------------------------------------ #


class _EmailMixin(BaseModel):
    email: str = Field(..., max_length=320)

    @field_validator("email")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_user_email(v)


class PasswordResetRequest(_EmailMixin):
    pass


class PasswordResetRequestResult(BaseModel):
    message: str
    # Seconds before another code may be requested
    resend_after: int
    # Only in SMS_DEV_MODE (never in production): the code, so the flow can be tested
    dev_code: Optional[str] = None


class PasswordResetVerify(_EmailMixin):
    code: str = Field(..., min_length=4, max_length=10)

    @field_validator("code", mode="before")
    @classmethod
    def _digits_only(cls, v):
        return re.sub(r"\s", "", str(v or ""))


class PasswordResetVerifyResult(BaseModel):
    # Single-use token that authorizes the password change for a few minutes
    reset_token: str
    expires_in: int


class PasswordResetConfirm(_EmailMixin):
    reset_token: str = Field(..., min_length=20, max_length=200)
    new_password: str = Field(..., max_length=PASSWORD_MAX_LENGTH + 1)
    confirm_password: str = Field(..., max_length=PASSWORD_MAX_LENGTH + 1)

    @model_validator(mode="after")
    def _strong_and_matching(self):
        problems = password_problems(self.new_password, self.email) + passwords_match_problems(
            self.new_password, self.confirm_password
        )
        if problems:
            raise ValueError(" · ".join(problems))
        return self
