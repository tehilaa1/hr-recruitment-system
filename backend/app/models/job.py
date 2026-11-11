from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

InterviewType = Literal["מרוכז", "יחידני"]


class JobCreate(BaseModel):
    job_title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    interviewers: List[str] = Field(default_factory=list)
    interview_location: str = ""
    interviewer_emails: List[str] = Field(default_factory=list)
    interview_type: InterviewType


class JobUpdate(BaseModel):
    job_title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    interviewers: Optional[List[str]] = None
    interview_location: Optional[str] = None
    interviewer_emails: Optional[List[str]] = None
    interview_type: Optional[InterviewType] = None


class JobResponse(BaseModel):
    id: str
    job_title: str
    description: str
    interviewers: List[str]
    interview_location: str
    interviewer_emails: List[str]
    interview_type: InterviewType
    created_at: datetime
    candidate_count: int = 0
