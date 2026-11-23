from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi import status as http_status

from app.dependencies import get_firestore_service, get_gemini_service
from app.models.candidate import REFERRER_MAX_LENGTH, clean_referrer
from app.models.talent_pool import (
    TalentPoolCandidateCreate,
    TalentPoolCandidateResponse,
    TalentPoolCandidateUpdate,
    TalentPoolUploadResult,
)
from app.security import AuthUser
from app.services.cv_file_service import CV_MAX_BYTES, cv_response, read_cv_upload
from app.services.cv_ingest_service import describe_duplicate, ingest_cvs
from app.services.dedup_service import CandidateDeduplicator
from app.services.demo_limits import (
    check_demo_record_cap,
    check_demo_uploads,
    consume_demo_ai,
    max_upload_bytes,
)
from app.services.firestore_service import FirestoreService
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/api/talent-pool", tags=["Talent Pool"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
AI = Annotated[GeminiService, Depends(get_gemini_service)]


@router.get("", response_model=list[TalentPoolCandidateResponse])
async def list_pool_candidates(user: AuthUser, db: DB):
    return await asyncio.to_thread(db.list_pool_candidates, user.tenant_id)


@router.post(
    "/upload",
    response_model=list[TalentPoolUploadResult],
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_to_pool(
    user: AuthUser,
    db: DB,
    ai: AI,
    files: list[UploadFile] = File(...),
    referred_by: str = Form("", max_length=REFERRER_MAX_LENGTH),
):
    """Parse CVs in parallel and add them to the pool (skipping people already in it)."""
    check_demo_uploads(user, files)
    existing = await asyncio.to_thread(db.list_pool_candidates, user.tenant_id)
    check_demo_record_cap(user, len(existing), len(files))
    consume_demo_ai(user, len(files))
    results = await ingest_cvs(
        files,
        ai,
        CandidateDeduplicator(existing),
        save=lambda data, cv: db.create_pool_candidate(user.tenant_id, data, cv),
        duplicate_message=lambda field, match: _duplicate_message(field, match)
        + " הקובץ לא נוסף.",
        extra_fields={"referred_by": clean_referrer(referred_by)},
    )
    return [TalentPoolUploadResult(**r) for r in results]


@router.post(
    "", response_model=TalentPoolCandidateResponse, status_code=http_status.HTTP_201_CREATED
)
async def create_pool_candidate(payload: TalentPoolCandidateCreate, user: AuthUser, db: DB):
    existing = await asyncio.to_thread(db.list_pool_candidates, user.tenant_id)
    check_demo_record_cap(user, len(existing))
    data = {**payload.model_dump(), "file_name": ""}
    match = CandidateDeduplicator(existing).find(data)
    if match:
        raise HTTPException(http_status.HTTP_409_CONFLICT, _duplicate_message(*match))
    return await asyncio.to_thread(db.create_pool_candidate, user.tenant_id, data)


@router.patch("/{candidate_id}", response_model=TalentPoolCandidateResponse)
async def update_pool_candidate(
    candidate_id: str, payload: TalentPoolCandidateUpdate, user: AuthUser, db: DB
):
    update = payload.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update")
    updated = await asyncio.to_thread(db.update_pool_candidate, user.tenant_id, candidate_id, update)
    if updated is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "המועמד לא נמצא במאגר")
    return updated


@router.get("/{candidate_id}/cv")
async def get_pool_cv(candidate_id: str, user: AuthUser, db: DB):
    """The pool entry's original CV file (404 if none was stored)."""
    return cv_response(await asyncio.to_thread(db.get_pool_cv, user.tenant_id, candidate_id))


@router.put("/{candidate_id}/cv", response_model=TalentPoolCandidateResponse)
async def attach_pool_cv(candidate_id: str, user: AuthUser, db: DB, file: UploadFile = File(...)):
    """Attach (or replace) the CV file of an existing pool entry. Details are not re-parsed."""
    cv = await read_cv_upload(file, max_upload_bytes(user, CV_MAX_BYTES))
    saved = await asyncio.to_thread(db.set_pool_cv, user.tenant_id, candidate_id, cv)
    if saved is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "המועמד לא נמצא במאגר")
    return saved


@router.delete("/{candidate_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_pool_candidate(candidate_id: str, user: AuthUser, db: DB):
    deleted = await asyncio.to_thread(db.delete_pool_candidate, user.tenant_id, candidate_id)
    if not deleted:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "המועמד לא נמצא במאגר")


def _duplicate_message(field: str, existing: dict) -> str:
    name, field_label, value = describe_duplicate(field, existing)
    return f"מועמד עם {field_label} ({value}) כבר קיים במאגר: {name}."
