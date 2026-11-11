from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

# Single source of truth for recruitment statuses (stored as-is in Firestore).
# Must stay identical, in the same order, to RECRUITMENT_STATUSES in
# frontend/src/constants/statuses.js; enforced by tests/test_status_sync.py.
VALID_STATUSES: tuple[str, ...] = (
    "לא טופל",
    "לא עונה",
    "נשלח זימון",
    "לשלוח זימון",
    "גויס/ה",  # Hired
    "שלילי",
    "לא רלוונטי",
)

DEFAULT_STATUS = VALID_STATUSES[0]

# Literal[...] built from the tuple above, so validation can't drift from it
RecruitmentStatus = Literal[VALID_STATUSES]  # type: ignore[valid-type]


class CandidateBase(BaseModel):
    full_name: str = ""
    family_name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    profession: str = ""
    years_of_experience: int = 0


class CandidateStatusUpdate(BaseModel):
    recruitment_status: RecruitmentStatus


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    family_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    profession: Optional[str] = None
    years_of_experience: Optional[int] = None
    recruitment_status: Optional[RecruitmentStatus] = None


class CandidateResponse(CandidateBase):
    id: str
    job_id: str
    recruitment_status: RecruitmentStatus
    file_name: str
    created_at: datetime


class CandidateApplication(BaseModel):
    """One candidate record = this person's application to one job."""

    candidate_id: str
    job_id: str
    job_title: str
    job_exists: bool = True
    interview_type: Optional[str] = None
    interview_location: str = ""
    recruitment_status: str
    file_name: str = ""
    created_at: Optional[datetime] = None


class CandidateProfile(BaseModel):
    """A person across all jobs (records merged by matching email or phone)."""

    key: str
    full_name: str = ""
    family_name: str = ""
    emails: list[str] = []
    phones: list[str] = []
    address: str = ""
    profession: str = ""
    years_of_experience: int = 0
    applications: list[CandidateApplication] = []


class CandidateUploadResult(BaseModel):
    file_name: str
    success: bool
    candidate: Optional[CandidateResponse] = None
    error: Optional[str] = None
    # True when the file was skipped because the candidate already exists for this job
    duplicate: bool = False
    duplicate_of_id: Optional[str] = None
