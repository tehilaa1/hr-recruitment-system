"""Global search across job candidates *and* the talent pool.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_search_talent_pool.py)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.candidate import CandidateProfile  # noqa: E402
from app.services.candidate_search_service import search_candidates  # noqa: E402

JOBS = {"j1": {"id": "j1", "job_title": "מפתח/ת", "interview_type": "יחידני"}}


def _at(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def _job_rec(cid, day, **f):
    return {"id": cid, "job_id": "j1", "recruitment_status": "לא טופל", "created_at": _at(day), **f}


def _pool_rec(pid, day, **f):
    return {"id": pid, "file_name": f"{pid}.pdf", "created_at": _at(day), **f}


def test_pool_only_candidate_is_found_and_flagged():
    pool = [_pool_rec("p1", 3, full_name="שירה", family_name="כהן", email="s@x.com")]
    [profile] = search_candidates("שירה", [], JOBS, pool_candidates=pool)
    assert profile["in_talent_pool"] is True
    assert profile["applications"] == []
    assert profile["talent_pool_entries"][0]["pool_id"] == "p1"
    CandidateProfile(**profile)  # valid response shape


def test_pool_and_job_records_merge_by_phone_or_email():
    jobs = [_job_rec("c1", 1, full_name="דנה", phone="050-1234567")]
    pool = [_pool_rec("p1", 5, full_name="דנה", family_name="לוי", phone="+972 50 123 4567", email="d@x.com")]
    [profile] = search_candidates("d@x.com", jobs, JOBS, pool_candidates=pool)
    assert profile["in_talent_pool"] is True
    assert [a["candidate_id"] for a in profile["applications"]] == ["c1"]
    assert profile["family_name"] == "לוי"  # most recent non-empty value (the pool record)
    assert profile["emails"] == ["d@x.com"]
    assert len(profile["phones"]) == 1


def test_job_only_candidate_is_not_flagged_and_pool_is_optional():
    jobs = [_job_rec("c1", 1, full_name="רון", email="r@x.com")]
    [profile] = search_candidates("רון", jobs, JOBS)
    assert profile["in_talent_pool"] is False
    assert profile["talent_pool_entries"] == []
    assert "_latest" not in profile and "_from_talent_pool" not in str(profile)


def test_results_sorted_by_most_recent_record_including_pool():
    jobs = [_job_rec("c1", 2, full_name="אבי", email="a1@x.com")]
    pool = [_pool_rec("p1", 9, full_name="אביגיל", email="a2@x.com")]
    keys = [p["key"] for p in search_candidates("אבי", jobs, JOBS, pool_candidates=pool)]
    assert keys == ["p1", "c1"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
