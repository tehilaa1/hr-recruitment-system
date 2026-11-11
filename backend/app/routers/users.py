from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.user import (
    UserCreate,
    UserCreateResult,
    UserResponse,
    UserUpdate,
    normalize_user_email,
)
from app.security import AdminUser, AuthUser
from app.services import auth_service
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

DB = Annotated[FirestoreService, Depends(get_firestore_service)]

# /api/auth/me – any authorized user
auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])

# /api/users – admins only (enforced per endpoint via AdminUser)
router = APIRouter(prefix="/api/users", tags=["User Management"])


@auth_router.get("/me", response_model=UserResponse)
async def get_me(user: AuthUser, db: DB):
    return await asyncio.to_thread(db.get_user, user.email)


@router.get("", response_model=list[UserResponse])
async def list_users(_: AdminUser, db: DB):
    users = await asyncio.to_thread(db.list_users)
    return sorted(users, key=lambda u: (u.get("role") != "admin", u["email"]))


@router.post("", response_model=UserCreateResult, status_code=http_status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, admin: AdminUser, db: DB):
    if await asyncio.to_thread(db.get_user, payload.email):
        raise HTTPException(http_status.HTTP_409_CONFLICT, "משתמש עם כתובת מייל זו כבר קיים")

    uid, created = await asyncio.to_thread(
        auth_service.get_or_create_account, payload.email, payload.display_name
    )
    data = {
        "display_name": payload.display_name.strip(),
        "role": payload.role,
        "uid": uid,
        "created_at": datetime.now(timezone.utc),
        "created_by": admin.email,
    }
    saved = await asyncio.to_thread(db.set_user, payload.email, data)
    logger.info("User %s added as %s by %s (new account: %s)", payload.email, payload.role, admin.email, created)
    return {"user": saved, "created_account": created}


@router.patch("/{email}", response_model=UserResponse)
async def update_user(email: str, payload: UserUpdate, admin: AdminUser, db: DB):
    email = normalize_user_email(email)
    existing = await _get_or_404(db, email)
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")

    if "role" in update and update["role"] != existing["role"]:
        if email == admin.email:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "לא ניתן לשנות את התפקיד של עצמך")
        await _ensure_not_last_admin(db, existing)

    return await asyncio.to_thread(db.update_user, email, update)


@router.delete("/{email}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_user(email: str, admin: AdminUser, db: DB):
    email = normalize_user_email(email)
    if email == admin.email:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "לא ניתן למחוק את המשתמש של עצמך")
    existing = await _get_or_404(db, email)
    await _ensure_not_last_admin(db, existing)

    await asyncio.to_thread(db.delete_user, email)
    if existing.get("uid"):
        # Remove the login itself, so access ends immediately and the email can be re-added cleanly
        await asyncio.to_thread(auth_service.delete_account, existing["uid"])
    logger.info("User %s removed by %s", email, admin.email)


async def _get_or_404(db: FirestoreService, email: str) -> dict:
    user = await asyncio.to_thread(db.get_user, email)
    if user is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "משתמש לא נמצא")
    return user


async def _ensure_not_last_admin(db: FirestoreService, user: dict) -> None:
    if user.get("role") == "admin" and await asyncio.to_thread(db.count_admins) <= 1:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "חייב להישאר לפחות מנהל/ת מערכת אחד/ת")
