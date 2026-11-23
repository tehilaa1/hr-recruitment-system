from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi import status as http_status

from app.dependencies import get_firestore_service, get_gemini_service
from app.models.candidate import (
    DEFAULT_STATUS,
    REFERRER_MAX_LENGTH,
    AssignFromPoolRequest,
    CandidateCompletionUpdate,
    CandidateCreate,
    CandidateResponse,
    CandidateStatusUpdate,
    CandidateUpdate,
    CandidateUploadResult,
    clean_referrer,
)
from app.security import AuthUser, CurrentUser
from app.services.cv_file_service import CV_MAX_BYTES, CvFile, cv_response, read_cv_upload
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs/{job_id}/candidates", tags=["Candidates"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
AI = Annotated[GeminiService, Depends(get_gemini_service)]

# Fields copied when a person enters a job from the talent pool or a manual form
_PERSON_FIELDS = (
    "full_name", "family_name", "phone", "email", "address", "profession", "years_of_experience",
)


# ------------------------------------------------------------------ #
# Upload & AI parse                                                    #
# ------------------------------------------------------------------ #


@router.post(
    "/upload",
    response_model=list[CandidateUploadResult],
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_candidates(
    job_id: str,
    user: AuthUser,
    db: DB,
    ai: AI,
    files: list[UploadFile] = File(...),
    referred_by: str = Form("", max_length=REFERRER_MAX_LENGTH),
):
    """Parse every CV in parallel (bounded by GEMINI_MAX_CONCURRENCY), then save.

    `referred_by` (optional) is recorded on every candidate of this batch.
    """
    await _assert_job(job_id, user, db)
    check_demo_uploads(user, files)

    existing = await asyncio.to_thread(db.list_candidates, user.tenant_id, job_id)
    check_demo_record_cap(user, len(existing), len(files))
    consume_demo_ai(user, len(files))
    results = await ingest_cvs(
        files,
        ai,
        CandidateDeduplicator(existing),
        save=lambda data, cv: db.create_candidate(user.tenant_id, job_id, data, cv),
        duplicate_message=_duplicate_message,
        extra_fields={
            "recruitment_status": DEFAULT_STATUS,
            "is_completed": False,
            "referred_by": clean_referrer(referred_by),
        },
    )
    return [CandidateUploadResult(**r) for r in results]


# ------------------------------------------------------------------ #
# Manual entry & assignment from the talent pool                      #
# ------------------------------------------------------------------ #


@router.post("", response_model=CandidateResponse, status_code=http_status.HTTP_201_CREATED)
async def create_candidate(job_id: str, payload: CandidateCreate, user: AuthUser, db: DB):
    """Add a candidate without a CV file (same duplicate check as uploads)."""
    await _assert_job(job_id, user, db)
    data = {**payload.model_dump(), "is_completed": False, "file_name": ""}
    return await _create_unless_duplicate(job_id, data, user, db)


@router.post(
    "/from-pool/{pool_candidate_id}",
    response_model=CandidateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def assign_from_pool(
    job_id: str,
    pool_candidate_id: str,
    user: AuthUser,
    db: DB,
    payload: Optional[AssignFromPoolRequest] = Body(None),
):
    """Copy a talent-pool candidate into this job (the pool record is kept).

    The pool entry's referrer is kept unless the body sets a different one.
    The pool entry's original CV file (if stored) is copied with it.
    """
    await _assert_job(job_id, user, db)
    pooled = await asyncio.to_thread(db.get_pool_candidate, user.tenant_id, pool_candidate_id)
    if pooled is None:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND, "המועמד לא נמצא במאגר"
        )
    data = {
        **{f: pooled.get(f, 0 if f == "years_of_experience" else "") for f in _PERSON_FIELDS},
        "recruitment_status": DEFAULT_STATUS,
        "is_completed": False,
        "file_name": pooled.get("file_name", ""),
        "source_pool_id": pool_candidate_id,
        "referred_by": (
            payload.referred_by
            if payload is not None and payload.referred_by is not None
            else clean_referrer(pooled.get("referred_by") or "")
        ),
    }
    cv = await asyncio.to_thread(db.get_pool_cv, user.tenant_id, pool_candidate_id)
    return await _create_unless_duplicate(job_id, data, user, db, cv)


# ------------------------------------------------------------------ #
# Original CV file                                                     #
# ------------------------------------------------------------------ #


@router.get("/{candidate_id}/cv")
async def get_candidate_cv(job_id: str, candidate_id: str, user: AuthUser, db: DB):
    """The candidate's original CV file (404 if none was stored)."""
    return cv_response(
        await asyncio.to_thread(db.get_candidate_cv, user.tenant_id, job_id, candidate_id)
    )


@router.put("/{candidate_id}/cv", response_model=CandidateResponse)
async def attach_candidate_cv(
    job_id: str, candidate_id: str, user: AuthUser, db: DB, file: UploadFile = File(...)
):
    """Attach (or replace) the CV file of an existing candidate. Details are not re-parsed."""
    cv = await read_cv_upload(file, max_upload_bytes(user, CV_MAX_BYTES))
    saved = await asyncio.to_thread(db.set_candidate_cv, user.tenant_id, job_id, candidate_id, cv)
    _assert_candidate(saved, candidate_id)
    return saved


# ------------------------------------------------------------------ #
# CRUD                                                                 #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(job_id: str, user: AuthUser, db: DB):
    await _assert_job(job_id, user, db)
    return await asyncio.to_thread(db.list_candidates, user.tenant_id, job_id)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(job_id: str, candidate_id: str, user: AuthUser, db: DB):
    candidate = await asyncio.to_thread(db.get_candidate, user.tenant_id, job_id, candidate_id)
    _assert_candidate(candidate, candidate_id)
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    job_id: str, candidate_id: str, payload: CandidateUpdate, user: AuthUser, db: DB
):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update"
        )
    result = await asyncio.to_thread(
        db.update_candidate, user.tenant_id, job_id, candidate_id, update_data
    )
    _assert_candidate(result, candidate_id)
    return result


@router.patch("/{candidate_id}/status", response_model=CandidateResponse)
async def update_candidate_status(
    job_id: str, candidate_id: str, payload: CandidateStatusUpdate, user: AuthUser, db: DB
):
    result = await asyncio.to_thread(
        db.update_candidate,
        user.tenant_id,
        job_id,
        candidate_id,
        {"recruitment_status": payload.recruitment_status},
    )
    _assert_candidate(result, candidate_id)
    return result


@router.patch("/{candidate_id}/complete", response_model=CandidateResponse)
async def update_candidate_completion(
    job_id: str, candidate_id: str, payload: CandidateCompletionUpdate, user: AuthUser, db: DB
):
    """Toggle "סיום טיפול" — the recruiter is done handling this candidate."""
    result = await asyncio.to_thread(
        db.update_candidate,
        user.tenant_id,
        job_id,
        candidate_id,
        {"is_completed": payload.is_completed},
    )
    _assert_candidate(result, candidate_id)
    return result


@router.delete("/{candidate_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_candidate(job_id: str, candidate_id: str, user: AuthUser, db: DB):
    deleted = await asyncio.to_thread(db.delete_candidate, user.tenant_id, job_id, candidate_id)
    if not deleted:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND, f"Candidate {candidate_id!r} not found"
        )


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _duplicate_message(field: str, existing: dict) -> str:
    name, field_label, value = describe_duplicate(field, existing)
    return f"מועמד עם {field_label} ({value}) כבר קיים במשרה: {name}. הקובץ לא נוסף."


async def _create_unless_duplicate(
    job_id: str,
    data: dict,
    user: CurrentUser,
    db: FirestoreService,
    cv: Optional[CvFile] = None,
) -> dict:
    existing = await asyncio.to_thread(db.list_candidates, user.tenant_id, job_id)
    check_demo_record_cap(user, len(existing))
    match = CandidateDeduplicator(existing).find(data)
    if match:
        field, existing_candidate = match
        name, field_label, value = describe_duplicate(field, existing_candidate)
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"מועמד עם {field_label} ({value}) כבר קיים במשרה: {name}.",
        )
    saved = await asyncio.to_thread(db.create_candidate, user.tenant_id, job_id, data, cv)
    if saved is None:  # the job was deleted meanwhile
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")
    return saved


async def _assert_job(job_id: str, user: CurrentUser, db: FirestoreService) -> None:
    job = await asyncio.to_thread(db.get_job, user.tenant_id, job_id)
    if job is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")


def _assert_candidate(candidate, candidate_id: str) -> None:
    if candidate is None:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND, f"Candidate {candidate_id!r} not found"
        )
