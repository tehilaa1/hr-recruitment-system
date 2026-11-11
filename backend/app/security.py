"""Authentication & authorization dependencies.

Every protected request must send `Authorization: Bearer <Firebase ID token>`.
The token is verified with the Firebase Admin SDK, then the caller is looked up
in the Firestore `users` collection (document id = lower-cased email). Access
is granted only if:
  * the user document exists (an admin authorized this email), and
  * its `uid` matches the token's uid. This binds the record to the account
    that was created for it, so someone who registers the same email elsewhere
    can't take it over.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.user import VALID_ROLES, normalize_user_email
from app.services import auth_service
from app.services.firestore_service import FirestoreService


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str
    role: str
    display_name: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        http_status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def get_current_user(
    db: Annotated[FirestoreService, Depends(get_firestore_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Missing bearer token")

    try:
        claims = await asyncio.to_thread(auth_service.verify_id_token, token)
    except auth_service.InvalidTokenError:
        raise _unauthorized("Invalid or expired token")

    email = normalize_user_email(claims.get("email", ""))
    if not email:
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "Account has no email")

    record = await asyncio.to_thread(db.get_user, email)
    if (
        record is None
        or record.get("role") not in VALID_ROLES
        or record.get("uid") != claims["uid"]
    ):
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "User is not authorized")

    return CurrentUser(
        uid=claims["uid"],
        email=email,
        role=record["role"],
        display_name=record.get("display_name", ""),
    )


def require_roles(*roles: str) -> Callable:
    """Dependency factory: allow only users whose role is in `roles`."""
    unknown = set(roles) - set(VALID_ROLES)
    if unknown:
        raise ValueError(f"Unknown roles: {unknown}")

    async def _check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(http_status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _check


# Ready-made dependencies
require_member = require_roles(*VALID_ROLES)  # any authorized user
require_admin = require_roles("admin")

AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
