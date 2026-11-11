from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.job import JobCreate, JobResponse, JobUpdate
from app.services.export_service import generate_xlsx
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]


# ------------------------------------------------------------------ #
# CRUD                                                                 #
# ------------------------------------------------------------------ #


@router.post("", response_model=JobResponse, status_code=http_status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, db: DB):
    result = await asyncio.to_thread(db.create_job, payload.model_dump())
    result["candidate_count"] = 0
    return result


@router.get("", response_model=list[JobResponse])
async def list_jobs(db: DB):
    jobs = await asyncio.to_thread(db.list_jobs)
    counts = await asyncio.gather(
        *[asyncio.to_thread(db.get_candidate_count, j["id"]) for j in jobs]
    )
    for job, count in zip(jobs, counts):
        job["candidate_count"] = count
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: DB):
    job = await asyncio.to_thread(db.get_job, job_id)
    _assert_job(job, job_id)
    job["candidate_count"] = await asyncio.to_thread(db.get_candidate_count, job_id)
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, payload: JobUpdate, db: DB):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update"
        )
    result = await asyncio.to_thread(db.update_job, job_id, update_data)
    _assert_job(result, job_id)
    result["candidate_count"] = await asyncio.to_thread(db.get_candidate_count, job_id)
    return result


@router.delete("/{job_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, db: DB):
    deleted = await asyncio.to_thread(db.delete_job, job_id)
    if not deleted:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")


# ------------------------------------------------------------------ #
# Export                                                               #
# ------------------------------------------------------------------ #


_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/{job_id}/export-excel")
async def export_candidates_excel(job_id: str, db: DB):
    job = await asyncio.to_thread(db.get_job, job_id)
    _assert_job(job, job_id)

    try:
        candidates = await asyncio.to_thread(db.list_candidates, job_id)
        xlsx_bytes = await asyncio.to_thread(generate_xlsx, candidates)
    except Exception:
        logger.exception("Excel export failed for job %s", job_id)
        raise HTTPException(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate Excel export"
        )

    return Response(
        content=xlsx_bytes,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": _content_disposition(str(job.get("job_title") or ""))
        },
    )


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _content_disposition(job_title: str) -> str:
    """Build a Content-Disposition header that survives non-ASCII (Hebrew) titles.

    HTTP headers must be latin-1, so the plain ``filename`` gets an ASCII-only
    fallback while ``filename*`` (RFC 5987) carries the real UTF-8 name.
    """
    title = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in job_title
    )[:50].strip("_") or "job"
    utf8_name = f"candidates_{title}.xlsx"
    ascii_title = "".join(c for c in title if c.isascii()).strip("_") or "job"
    ascii_name = f"candidates_{ascii_title}.xlsx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(utf8_name)}"


def _assert_job(job, job_id: str) -> None:
    if job is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")
