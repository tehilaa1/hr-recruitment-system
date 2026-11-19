from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.dependencies import get_firestore_service
from app.models.candidate import CandidateProfile
from app.services.candidate_search_service import (
    find_person,
    list_people,
    list_referrers,
    search_candidates,
)
from app.services.firestore_service import FirestoreService

router = APIRouter(prefix="/api/candidates", tags=["Global Candidates"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]


@router.get("", response_model=list[CandidateProfile])
async def list_all_people(db: DB):
    """Every candidate as one person: all job applications and talent-pool entries,
    merged by email or phone, most recently active first.

    Computed on each request from the job candidates and the talent pool (the
    sources of truth), so it never drifts from them.
    """
    candidates, jobs, pool = await _load_all(db)
    return list_people(candidates, {j["id"]: j for j in jobs}, pool_candidates=pool)


@router.get("/referrers", response_model=list[str])
async def referrer_suggestions(db: DB):
    """Referrer names already used (applications + talent pool), most used first."""
    candidates, pool = await asyncio.gather(
        asyncio.to_thread(db.list_all_candidates),
        asyncio.to_thread(db.list_pool_candidates),
    )
    return list_referrers(candidates + pool)


@router.get("/search", response_model=list[CandidateProfile])
async def global_candidate_search(
    db: DB,
    q: str = Query(..., min_length=2, max_length=100, description="Name, email or phone"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search candidates across *all* jobs and the talent pool.

    Records sharing an email or phone are merged into one profile that lists
    every position the person applied to (with their status in each) and
    whether they are also in the talent pool.
    """
    candidates, jobs, pool = await _load_all(db)
    jobs_by_id = {j["id"]: j for j in jobs}
    return search_candidates(q, candidates, jobs_by_id, limit=limit, pool_candidates=pool)


@router.get("/by-record/{record_id}", response_model=CandidateProfile)
async def person_by_record(record_id: str, db: DB):
    """The merged profile of the person owning this record (a job-candidate or talent-pool id).

    Lets the UI refresh one profile after editing, assigning or removing one of its records.
    """
    candidates, jobs, pool = await _load_all(db)
    profile = find_person(record_id, candidates, {j["id"]: j for j in jobs}, pool_candidates=pool)
    if profile is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "המועמד לא נמצא")
    return profile


async def _load_all(db: FirestoreService):
    return await asyncio.gather(
        asyncio.to_thread(db.list_all_candidates),
        asyncio.to_thread(db.list_jobs),
        asyncio.to_thread(db.list_pool_candidates),
    )
