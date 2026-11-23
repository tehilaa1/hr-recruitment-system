from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.maternity import (
    MaternityLeaveCreate,
    MaternityLeaveResponse,
    MaternityLeaveUpdate,
    MaternitySettings,
)
from app.services.export_service import (
    XLSX_MEDIA_TYPE,
    content_disposition,
    generate_maternity_xlsx,
)
from app.security import AuthUser
from app.services.demo_limits import check_demo_record_cap
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/maternity", tags=["Maternity Leave"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]

_SETTINGS_DOC = "maternity"


# ------------------------------------------------------------------ #
# Settings (fixed notification recipients, Teams channel)             #
# Declared before /{record_id} routes so "settings" isn't read as id  #
# ------------------------------------------------------------------ #


@router.get("/settings", response_model=MaternitySettings)
async def get_maternity_settings(user: AuthUser, db: DB):
    data = await asyncio.to_thread(db.get_settings_doc, user.tenant_id, _SETTINGS_DOC)
    return MaternitySettings.model_validate(data) if data else MaternitySettings()


@router.put("/settings", response_model=MaternitySettings)
async def update_maternity_settings(payload: MaternitySettings, user: AuthUser, db: DB):
    data = payload.model_dump()
    if "templates" not in payload.model_fields_set:
        # A client that doesn't know about templates must not wipe the saved ones
        stored = await asyncio.to_thread(db.get_settings_doc, user.tenant_id, _SETTINGS_DOC)
        data["templates"] = MaternitySettings.model_validate(stored).templates.model_dump()
    await asyncio.to_thread(db.set_settings_doc, user.tenant_id, _SETTINGS_DOC, data)
    return MaternitySettings.model_validate(data)


# ------------------------------------------------------------------ #
# Excel export (privacy-filtered; see MATERNITY_EXPORT_COLUMNS)        #
# ------------------------------------------------------------------ #


@router.get("/export-excel")
async def export_maternity_excel(user: AuthUser, db: DB):
    """Every record, open ones first. Gift address and delivery contact are never exported."""
    try:
        records = await asyncio.to_thread(db.list_maternity_leaves, user.tenant_id)
        records.sort(key=lambda r: bool(r.get("is_completed")))  # stable: keeps newest-first
        xlsx_bytes = await asyncio.to_thread(generate_maternity_xlsx, records)
    except Exception:
        logger.exception("Maternity Excel export failed")
        raise HTTPException(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate Excel export"
        )
    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition("maternity_leaves", date.today().isoformat())},
    )


# ------------------------------------------------------------------ #
# Records                                                              #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[MaternityLeaveResponse])
async def list_maternity_leaves(user: AuthUser, db: DB):
    return await asyncio.to_thread(db.list_maternity_leaves, user.tenant_id)


@router.post(
    "", response_model=MaternityLeaveResponse, status_code=http_status.HTTP_201_CREATED
)
async def create_maternity_leave(payload: MaternityLeaveCreate, user: AuthUser, db: DB):
    if user.is_demo:
        existing = await asyncio.to_thread(db.list_maternity_leaves, user.tenant_id)
        check_demo_record_cap(user, len(existing))
    # mode="json" stores dates as "YYYY-MM-DD" strings (Firestore has no date-only type)
    return await asyncio.to_thread(
        db.create_maternity_leave, user.tenant_id, payload.model_dump(mode="json")
    )


@router.patch("/{record_id}", response_model=MaternityLeaveResponse)
async def update_maternity_leave(
    record_id: str, payload: MaternityLeaveUpdate, user: AuthUser, db: DB
):
    update_data = payload.model_dump(mode="json", exclude_unset=True)
    if not update_data:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "Name is required")
    result = await asyncio.to_thread(db.update_maternity_leave, user.tenant_id, record_id, update_data)
    if result is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Record {record_id!r} not found")
    return result


@router.delete("/{record_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_maternity_leave(record_id: str, user: AuthUser, db: DB):
    deleted = await asyncio.to_thread(db.delete_maternity_leave, user.tenant_id, record_id)
    if not deleted:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Record {record_id!r} not found")
