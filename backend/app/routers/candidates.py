from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi import status as http_status

from app.dependencies import get_firestore_service, get_gemini_service
from app.models.candidate import (
    DEFAULT_STATUS,
    CandidateResponse,
    CandidateStatusUpdate,
    CandidateUpdate,
    CandidateUploadResult,
)
from app.services.dedup_service import CandidateDeduplicator
from app.services.firestore_service import FirestoreService
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs/{job_id}/candidates", tags=["Candidates"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]
AI = Annotated[GeminiService, Depends(get_gemini_service)]

_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "docx", "doc"}


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
    db: DB,
    ai: AI,
    files: list[UploadFile] = File(...),
):
    job = await asyncio.to_thread(db.get_job, job_id)
    if job is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")

    existing = await asyncio.to_thread(db.list_candidates, job_id)
    dedup = CandidateDeduplicator(existing)

    results: list[CandidateUploadResult] = []

    for upload in files:
        file_name = upload.filename or "unknown"
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        if ext not in _ALLOWED_EXTENSIONS:
            results.append(
                CandidateUploadResult(
                    file_name=file_name,
                    success=False,
                    error=(
                        f"Unsupported extension '.{ext}'. "
                        f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
                    ),
                )
            )
            continue

        try:
            content = await upload.read()
            content_type = upload.content_type or "application/octet-stream"

            parsed = await asyncio.to_thread(ai.parse_cv, content, file_name, content_type)

            match = dedup.find(parsed)
            if match:
                field, existing_candidate = match
                logger.info(
                    "Skipping duplicate candidate from %r for job %s (matched on %s, existing id %s)",
                    file_name, job_id, field, existing_candidate.get("id"),
                )
                results.append(
                    CandidateUploadResult(
                        file_name=file_name,
                        success=False,
                        duplicate=True,
                        duplicate_of_id=existing_candidate.get("id"),
                        error=_duplicate_message(field, existing_candidate),
                    )
                )
                continue

            candidate_data = {
                **parsed,
                "recruitment_status": DEFAULT_STATUS,
                "file_name": file_name,
            }
            saved = await asyncio.to_thread(db.create_candidate, job_id, candidate_data)
            dedup.add(saved)
            results.append(
                CandidateUploadResult(
                    file_name=file_name,
                    success=True,
                    candidate=CandidateResponse(**saved),
                )
            )

        except Exception as exc:
            logger.exception("Failed to process file %r for job %s", file_name, job_id)
            results.append(
                CandidateUploadResult(file_name=file_name, success=False, error=str(exc))
            )

    return results


# ------------------------------------------------------------------ #
# CRUD                                                                 #
# ------------------------------------------------------------------ #


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(job_id: str, db: DB):
    await _assert_job(job_id, db)
    return await asyncio.to_thread(db.list_candidates, job_id)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(job_id: str, candidate_id: str, db: DB):
    candidate = await asyncio.to_thread(db.get_candidate, job_id, candidate_id)
    _assert_candidate(candidate, candidate_id)
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    job_id: str, candidate_id: str, payload: CandidateUpdate, db: DB
):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY, "No fields to update"
        )
    result = await asyncio.to_thread(
        db.update_candidate, job_id, candidate_id, update_data
    )
    _assert_candidate(result, candidate_id)
    return result


@router.patch("/{candidate_id}/status", response_model=CandidateResponse)
async def update_candidate_status(
    job_id: str, candidate_id: str, payload: CandidateStatusUpdate, db: DB
):
    result = await asyncio.to_thread(
        db.update_candidate,
        job_id,
        candidate_id,
        {"recruitment_status": payload.recruitment_status},
    )
    _assert_candidate(result, candidate_id)
    return result


@router.delete("/{candidate_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_candidate(job_id: str, candidate_id: str, db: DB):
    deleted = await asyncio.to_thread(db.delete_candidate, job_id, candidate_id)
    if not deleted:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND, f"Candidate {candidate_id!r} not found"
        )


# ------------------------------------------------------------------ #
# Private                                                              #
# ------------------------------------------------------------------ #


def _duplicate_message(field: str, existing: dict) -> str:
    name = " ".join(
        p for p in (existing.get("full_name"), existing.get("family_name")) if p
    ) or "ללא שם"
    field_label = "אותה כתובת מייל" if field == "email" else "אותו מספר טלפון"
    value = existing.get("email") if field == "email" else existing.get("phone")
    return f"מועמד עם {field_label} ({value}) כבר קיים במשרה: {name}. הקובץ לא נוסף."


async def _assert_job(job_id: str, db: FirestoreService) -> None:
    job = await asyncio.to_thread(db.get_job, job_id)
    if job is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Job {job_id!r} not found")


def _assert_candidate(candidate, candidate_id: str) -> None:
    if candidate is None:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND, f"Candidate {candidate_id!r} not found"
        )
