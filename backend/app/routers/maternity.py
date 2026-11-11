from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.maternity import (
    MaternityLeaveCreate,
    MaternityLeaveResponse,
    MaternityLeaveUpdate,
    MaternitySettings,
)
from app.services.firestore_service import FirestoreService

router = APIRouter(prefix="/api/maternity", tags=["Maternity Leave"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]

_SETTINGS_DOC = "maternity"


# ------------------------------------------------------------------ #
# Settings (fixed notification recipients, Teams channel)             #
# Declared before /{record_id} routes so "settings" isn't read as id  #
# ------------------------------------------------------------------ #


@router.get("/settings", response_model=MaternitySettings)
async def get_maternity_settings(db: DB):
    data = await asyncio.to_thread(db.get_settings_doc, _SETTINGS_DOC)
    return MaternitySettings.model_validate(data) if data else MaternitySettings()


@router.put("/settings", response_model=MaternitySettings)
async def update_maternity_settings(payload: MaternitySettings, db: DB):
    await asyncio.to_thread(db.set_settings_doc, _SETTINGS_DOC, payload.model_dump())
    return payload


# ------------------------------------------------------------------ #
# Records                                                              #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[MaternityLeaveResponse])
async def list_maternity_leaves(db: DB):
    return await asyncio.to_thread(db.list_maternity_leaves)


@router.post(
    "", response_model=MaternityLeaveResponse, status_code=http_status.HTTP_201_CREATED
)
async def create_maternity_leave(payload: MaternityLeaveCreate, db: DB):
    # mode="json" stores dates as "YYYY-MM-DD" strings (Firestore has no date-only type)
    return await asyncio.to_thread(
        db.create_maternity_leave, payload.model_dump(mode="json")
    )


@router.patch("/{record_id}", response_model=MaternityLeaveResponse)
async def update_maternity_leave(record_id: str, payload: MaternityLeaveUpdate, db: DB):
    update_data = payload.model_dump(mode="json", exclude_unset=True)
    if not update_data:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "Name is required")
    result = await asyncio.to_thread(db.update_maternity_leave, record_id, update_data)
    if result is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Record {record_id!r} not found")
    return result


@router.delete("/{record_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_maternity_leave(record_id: str, db: DB):
    deleted = await asyncio.to_thread(db.delete_maternity_leave, record_id)
    if not deleted:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Record {record_id!r} not found")
