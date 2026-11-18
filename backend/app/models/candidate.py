from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

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

# "הובא על ידי" — the employee who referred the candidate (חבר מביא חבר).
# Free text, recorded per application: the same person can be referred to
# different jobs by different employees.
REFERRER_MAX_LENGTH = 100


def clean_referrer(value):
    """Trim and collapse inner whitespace, so "  יוסי   לוי " and "יוסי לוי" are one referrer."""
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else value


class CandidateBase(BaseModel):
    full_name: str = ""
    family_name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    profession: str = ""
    years_of_experience: int = 0
    referred_by: str = ""


class CandidateManualBase(BaseModel):
    """Details typed in by a recruiter (no CV file). A first name is required."""

    full_name: str = Field(..., max_length=100)
    family_name: str = Field("", max_length=100)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=200)
    address: str = Field("", max_length=300)
    profession: str = Field("", max_length=200)
    years_of_experience: int = Field(0, ge=0, le=70)
    referred_by: str = Field("", max_length=REFERRER_MAX_LENGTH)

    @field_validator(
        "full_name", "family_name", "phone", "email", "address", "profession", mode="before"
    )
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    _referrer = field_validator("referred_by", mode="before")(clean_referrer)

    @field_validator("full_name")
    @classmethod
    def _require_name(cls, v: str) -> str:
        if not v:
            raise ValueError("שם פרטי הוא שדה חובה")
        return v


class CandidateCreate(CandidateManualBase):
    """Manual candidate entry for a job."""

    recruitment_status: RecruitmentStatus = DEFAULT_STATUS


class CandidateStatusUpdate(BaseModel):
    recruitment_status: RecruitmentStatus


class CandidateCompletionUpdate(BaseModel):
    is_completed: bool


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    family_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    profession: Optional[str] = None
    years_of_experience: Optional[int] = None
    recruitment_status: Optional[RecruitmentStatus] = None
    is_completed: Optional[bool] = None
    referred_by: Optional[str] = Field(None, max_length=REFERRER_MAX_LENGTH)  # "" clears it

    _referrer = field_validator("referred_by", mode="before")(clean_referrer)


class AssignFromPoolRequest(BaseModel):
    """Optional body when copying a talent-pool candidate into a job.

    referred_by None (or no body) keeps the referrer recorded in the pool.
    """

    referred_by: Optional[str] = Field(None, max_length=REFERRER_MAX_LENGTH)

    _referrer = field_validator("referred_by", mode="before")(clean_referrer)


class CandidateResponse(CandidateBase):
    id: str
    job_id: str
    recruitment_status: RecruitmentStatus
    # "סיום טיפול" — recruiter is done with this candidate (missing in older records)
    is_completed: bool = False
    file_name: str = ""
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
    is_completed: bool = False
    referred_by: str = ""
    file_name: str = ""
    created_at: Optional[datetime] = None


class TalentPoolEntry(BaseModel):
    """This person's record in the global talent pool."""

    pool_id: str
    file_name: str = ""
    referred_by: str = ""
    created_at: Optional[datetime] = None


class CandidateProfile(BaseModel):
    """A person across all jobs and the talent pool (records merged by email or phone)."""

    key: str
    full_name: str = ""
    family_name: str = ""
    emails: list[str] = []
    phones: list[str] = []
    address: str = ""
    profession: str = ""
    years_of_experience: int = 0
    # Newest first: job, application date, current status and referrer per application
    applications: list[CandidateApplication] = []
    in_talent_pool: bool = False
    talent_pool_entries: list[TalentPoolEntry] = []
    # Everyone who referred this person (any application or pool entry), most recent first
    referrers: list[str] = []
    last_activity: Optional[datetime] = None


class CandidateUploadResult(BaseModel):
    file_name: str
    success: bool
    candidate: Optional[CandidateResponse] = None
    error: Optional[str] = None
    # True when the file was skipped because the candidate already exists for this job
    duplicate: bool = False
    duplicate_of_id: Optional[str] = None
