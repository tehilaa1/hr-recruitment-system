from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_firestore_service
from app.models.candidate import CandidateProfile
from app.services.candidate_search_service import search_candidates
from app.services.firestore_service import FirestoreService

router = APIRouter(prefix="/api/candidates", tags=["Global Search"])

DB = Annotated[FirestoreService, Depends(get_firestore_service)]


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
    candidates, jobs, pool = await asyncio.gather(
        asyncio.to_thread(db.list_all_candidates),
        asyncio.to_thread(db.list_jobs),
        asyncio.to_thread(db.list_pool_candidates),
    )
    jobs_by_id = {j["id"]: j for j in jobs}
    return search_candidates(q, candidates, jobs_by_id, limit=limit, pool_candidates=pool)
