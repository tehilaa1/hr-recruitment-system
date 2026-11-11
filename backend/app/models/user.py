from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Must stay identical to ROLES in frontend/src/constants/roles.js
# (enforced by tests/test_roles_sync.py).
#   admin  – full access + user management
#   editor – full access to jobs, candidates and maternity data
VALID_ROLES: tuple[str, ...] = ("admin", "editor")

Role = Literal[VALID_ROLES]  # type: ignore[valid-type]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_user_email(email: str) -> str:
    return (email or "").strip().lower()


class UserCreate(BaseModel):
    email: str
    display_name: str = Field("", max_length=100)
    role: Role = "editor"

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = normalize_user_email(v)
        if not _EMAIL_RE.match(v):
            raise ValueError("כתובת מייל לא תקינה")
        return v


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    role: Optional[Role] = None


class UserResponse(BaseModel):
    email: str
    display_name: str = ""
    role: Role
    uid: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


class UserCreateResult(BaseModel):
    user: UserResponse
    # False when a Firebase Auth account with this email already existed
    created_account: bool
