from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status

from app.dependencies import get_firestore_service, get_gemini_service
from app.models.job import JobCreate, JobResponse, JobUpdate
from app.models.talent_pool import PoolMatch
from app.security import AuthUser
from app.services.dedup_service import exclude_existing
from app.services.demo_limits import check_demo_record_cap, consume_demo_ai
from app.services.export_service import XLSX_MEDIA_TYPE, content_disposition, generate_xlsx
from app.services.firestore_service import FirestoreService
from app.services.gemini_service import GeminiParseError, GeminiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
AI = Annotated[GeminiService, Depends(get_gemini_service)]


# ------------------------------------------------------------------ #
# CRUD                                                                 #
# ------------------------------------------------------------------ #


@router.post("", response_model=JobResponse, status_code=http_status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, user: AuthUser, db: DB):
    if user.is_demo:
        existing = await asyncio.to_thread(db.list_jobs, user.tenant_id)
        check_demo_record_cap(user, len(existing))
    result = await asyncio.to_thread(db.create_job, user.tenant_id, payload.model_dump())
    result["candidate_count"] = 0
    return result


@router.get("", response_model=list[JobResponse])
async def list_jobs(user: AuthUser, db: DB):
    jobs = await asyncio.to_thread(db.list_jobs, user.tenant_id)
    counts = await asyncio.gather(
        *[asyncio.to_thread(db.get_candidate_count, user.tenant_id, j["id"]) for j in jobs]
    )
    for job, count in zip(jobs, counts):
        job["candidate_count"] = count
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user: AuthUser, db: DB):
    job = await asyncio.to_thread(db.get_job, user.tenant_id, job_id)
    _assert_job(job, job_id)
    job["candidate_count"] = await asyncio.to_thread(db.get_candidate_count, user.tenant_id, job_id)
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, payload: JobUpdate, user: AuthUser, db: DB):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update"
        )
    result = await asyncio.to_thread(db.update_job, user.tenant_id, job_id, update_data)
    _assert_job(result, job_id)
    result["candidate_count"] = await asyncio.to_thread(db.get_candidate_count, user.tenant_id, job_id)
    return result


@router.delete("/{job_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, user: AuthUser, db: DB):
    deleted = await asyncio.to_thread(db.delete_job, user.tenant_id, job_id)
    if not deleted:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")


# ------------------------------------------------------------------ #
# AI matching against the talent pool                                  #
# ------------------------------------------------------------------ #


@router.post("/{job_id}/match-pool", response_model=list[PoolMatch])
async def match_pool_candidates(
    job_id: str, user: AuthUser, db: DB, ai: AI, limit: int = Query(5, ge=1, le=10)
):
    """Suggest talent-pool candidates for this job, with a Hebrew reason for each.

    People who already applied to the job (same normalized email/phone) are excluded.
    """
    job = await asyncio.to_thread(db.get_job, user.tenant_id, job_id)
    _assert_job(job, job_id)

    pool, applied = await asyncio.gather(
        asyncio.to_thread(db.list_pool_candidates, user.tenant_id),
        asyncio.to_thread(db.list_candidates, user.tenant_id, job_id),
    )
    available = exclude_existing(pool, applied)
    if not available:
        return []
    consume_demo_ai(user)

    try:
        ranked = await asyncio.to_thread(
            ai.match_candidates,
            str(job.get("job_title") or ""),
            str(job.get("description") or ""),
            available,
            limit,
        )
    except GeminiParseError as exc:
        raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, str(exc))

    by_id = {c["id"]: c for c in available}
    return [
        PoolMatch(candidate=by_id[m["id"]], score=m["score"], match_reason=m["match_reason"])
        for m in ranked
    ]


# ------------------------------------------------------------------ #
# Export                                                               #
# ------------------------------------------------------------------ #


@router.get("/{job_id}/export-excel")
async def export_candidates_excel(job_id: str, user: AuthUser, db: DB):
    job = await asyncio.to_thread(db.get_job, user.tenant_id, job_id)
    _assert_job(job, job_id)

    try:
        candidates = await asyncio.to_thread(db.list_candidates, user.tenant_id, job_id)
        xlsx_bytes = await asyncio.to_thread(generate_xlsx, candidates)
    except Exception:
        logger.exception("Excel export failed for job %s", job_id)
        raise HTTPException(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate Excel export"
        )

    return Response(
        content=xlsx_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": content_disposition(
                "candidates", str(job.get("job_title") or "") or "job"
            )
        },
    )


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _assert_job(job, job_id: str) -> None:
    if job is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")
