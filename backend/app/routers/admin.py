"""Super-admin operations (``users/{email}.is_super_admin``, set only by the CLI scripts).

    GET  /api/admin/tenants        list workspaces
    POST /api/admin/tenants        create a new isolated workspace + its first admin
    POST /api/admin/demo/reset     wipe and re-seed the public demo workspace

Being a super admin grants no access to other workspaces' data: every data
endpoint stays scoped to the caller's own tenant_id.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.dependencies import get_firestore_service
from app.models.user import UserCreate
from app.security import SuperAdminUser
from app.services import auth_service
from app.services.demo_limits import demo_ai_counter
from app.services.demo_seed import reset_demo
from app.services.firestore_service import FirestoreService, check_owner_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Super Admin"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Optional readable id ("acme"); a random one is generated if omitted
    tenant_id: Optional[str] = Field(None, max_length=64)
    admin_email: str
    admin_display_name: str = Field("", max_length=100)
    admin_phone: str = ""

    @field_validator("tenant_id")
    @classmethod
    def _valid_tenant_id(cls, v):
        if v is None or v == "":
            return None
        try:
            return check_owner_id(v.strip().lower())
        except ValueError:
            raise ValueError("מזהה סביבת עבודה: אותיות לועזיות, ספרות ומקפים בלבד")


class TenantResponse(BaseModel):
    id: str
    name: str = ""
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    is_demo: bool = False


class TenantCreateResult(BaseModel):
    tenant: TenantResponse
    admin_email: str
    created_account: bool


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(_: SuperAdminUser, db: DB):
    demo_id = get_settings().DEMO_TENANT_ID
    tenants = await asyncio.to_thread(db.list_tenants)
    return [{**t, "is_demo": t["id"] == demo_id} for t in tenants]


@router.post("/tenants", response_model=TenantCreateResult, status_code=http_status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, admin: SuperAdminUser, db: DB):
    """A new, empty workspace whose first admin can then invite their own team."""
    # Same validation/normalization as adding a user from the UI
    user = UserCreate(
        email=payload.admin_email,
        display_name=payload.admin_display_name,
        role="admin",
        phone=payload.admin_phone,
    )
    tenant_id = payload.tenant_id or f"ws-{secrets.token_hex(6)}"
    if tenant_id == get_settings().DEMO_TENANT_ID:
        raise HTTPException(http_status.HTTP_409_CONFLICT, "מזהה זה שמור לסביבת ההדגמה")
    if await asyncio.to_thread(db.get_tenant, tenant_id):
        raise HTTPException(http_status.HTTP_409_CONFLICT, "סביבת עבודה עם מזהה זה כבר קיימת")
    if await asyncio.to_thread(db.get_user, user.email):
        # Users belong to exactly one workspace
        raise HTTPException(http_status.HTTP_409_CONFLICT, "משתמש עם כתובת מייל זו כבר קיים")

    uid, created = await asyncio.to_thread(
        auth_service.get_or_create_account, user.email, user.display_name
    )
    now = datetime.now(timezone.utc)
    tenant = await asyncio.to_thread(
        db.set_tenant, tenant_id, {"name": payload.name.strip(), "created_at": now, "created_by": admin.email}
    )
    await asyncio.to_thread(
        db.set_user,
        user.email,
        {
            "display_name": user.display_name.strip(),
            "role": "admin",
            "phone": user.phone,
            "uid": uid,
            "tenant_id": tenant_id,
            "created_at": now,
            "created_by": admin.email,
        },
    )
    logger.info("Workspace %s created by %s with admin %s", tenant_id, admin.email, user.email)
    return {"tenant": tenant, "admin_email": user.email, "created_account": created}


@router.post("/demo/reset")
async def reset_demo_workspace(admin: SuperAdminUser, db: DB):
    """Delete everything in the demo workspace (only there) and load the sample data again."""
    demo_id = get_settings().DEMO_TENANT_ID
    result = await asyncio.to_thread(reset_demo, db, demo_id, demo_id)
    demo_ai_counter.reset()
    logger.warning("Demo workspace reset by %s: %s", admin.email, result)
    return result
