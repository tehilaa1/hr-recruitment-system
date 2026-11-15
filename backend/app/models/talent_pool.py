from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.candidate import CandidateBase, CandidateManualBase


class TalentPoolCandidateCreate(CandidateManualBase):
    """Manual entry into the talent pool (no CV file)."""


class TalentPoolCandidateResponse(CandidateBase):
    """A CV kept in the global `talent_pool` collection, not tied to any job."""

    id: str
    file_name: str = ""
    created_at: datetime


class TalentPoolUploadResult(BaseModel):
    file_name: str
    success: bool
    candidate: Optional[TalentPoolCandidateResponse] = None
    error: Optional[str] = None
    # True when the file was skipped because the person is already in the pool
    duplicate: bool = False
    duplicate_of_id: Optional[str] = None


class PoolMatch(BaseModel):
    """A talent-pool candidate the AI suggests for a job."""

    candidate: TalentPoolCandidateResponse
    score: int
    match_reason: str  # Hebrew, specific to the job
