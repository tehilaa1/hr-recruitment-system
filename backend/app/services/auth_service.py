"""Firebase Authentication (Admin SDK) operations.

Requires firebase_admin to be initialized, which FirestoreService does on
construction, so callers get it via the get_firestore_service dependency.
"""
from __future__ import annotations

import secrets
from typing import Optional

from firebase_admin import auth


class InvalidTokenError(Exception):
    pass


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token (signature, expiry, audience) and return its claims."""
    try:
        return auth.verify_id_token(id_token)
    except (
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.CertificateFetchError,
        auth.UserDisabledError,
        ValueError,
    ) as exc:
        raise InvalidTokenError(str(exc)) from exc


def get_or_create_account(
    email: str, display_name: str = "", password: Optional[str] = None
) -> tuple[str, bool]:
    """Return (uid, created). New accounts get a random password unless one is
    given; the user then sets their own via the "reset password" email."""
    try:
        return auth.get_user_by_email(email).uid, False
    except auth.UserNotFoundError:
        pass
    user = auth.create_user(
        email=email,
        password=password or secrets.token_urlsafe(24),
        display_name=display_name or None,
    )
    return user.uid, True


def delete_account(uid: str) -> None:
    try:
        auth.delete_user(uid)
    except auth.UserNotFoundError:
        pass


def revoke_sessions(uid: str) -> None:
    try:
        auth.revoke_refresh_tokens(uid)
    except auth.UserNotFoundError:
        pass
