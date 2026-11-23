""""Referred by" (הובא על ידי) and the unified candidate profile.

Runs the real routers + FirestoreService on an in-memory Firestore stand-in,
with a stub CV parser instead of Gemini.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_referrals.py)
"""
from __future__ import annotations

import io
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from app.dependencies import get_firestore_service, get_gemini_service  # noqa: E402
from app.models.candidate import (  # noqa: E402
    REFERRER_MAX_LENGTH,
    CandidateCreate,
    CandidateUpdate,
)
from app.routers import candidates, jobs, search, talent_pool  # noqa: E402
from app.services.candidate_search_service import list_people, list_referrers  # noqa: E402
from fake_firestore import fake_service, sign_in  # noqa: E402

FRONTEND_SRC = BACKEND_DIR.parent / "frontend" / "src"


class _StubAI:
    """parse_cv_async returns the person encoded in the file name: "first|last|email|phone.pdf"."""

    async def parse_cv_async(self, content, file_name, content_type):
        first, last, email, phone = file_name.rsplit(".", 1)[0].split("|")
        return {"full_name": first, "family_name": last, "email": email, "phone": phone,
                "address": "", "profession": "", "years_of_experience": 0}


def _setup():
    fake, db = fake_service()
    app = FastAPI()
    for r in (jobs, candidates, search, talent_pool):
        app.include_router(r.router)
    app.dependency_overrides[get_firestore_service] = lambda: db
    app.dependency_overrides[get_gemini_service] = lambda: _StubAI()
    sign_in(app)
    client = TestClient(app)
    job_a = client.post("/api/jobs", json={"job_title": "מפתח/ת Python", "description": "x", "interview_type": "יחידני"}).json()["id"]
    job_b = client.post("/api/jobs", json={"job_title": "מנהל/ת מוצר", "description": "x", "interview_type": "יחידני"}).json()["id"]
    return fake, db, client, job_a, job_b


def _cv(first, last, email, phone):
    return ("files", (f"{first}|{last}|{email}|{phone}.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))


def _person(client, email):
    people = client.get("/api/candidates").json()
    return next(p for p in people if email in p["emails"])


# ------------------------------------------------------------------ #
# Models                                                               #
# ------------------------------------------------------------------ #


def test_referrer_is_cleaned_and_limited():
    assert CandidateCreate(full_name="דנה", referred_by="  יוסי \t  לוי ").referred_by == "יוסי לוי"
    assert CandidateCreate(full_name="דנה").referred_by == ""
    assert CandidateUpdate(referred_by="").model_dump(exclude_none=True) == {"referred_by": ""}
    try:
        CandidateCreate(full_name="x", referred_by="א" * (REFERRER_MAX_LENGTH + 1))
    except ValueError:
        pass
    else:
        raise AssertionError("expected a length error")


def test_frontend_referrer_limit_matches_backend():
    source = (FRONTEND_SRC / "constants" / "referrals.js").read_text(encoding="utf-8")
    match = re.search(r"export const REFERRER_MAX_LENGTH\s*=\s*(\d+);", source)
    assert match and int(match.group(1)) == REFERRER_MAX_LENGTH


# ------------------------------------------------------------------ #
# Service                                                              #
# ------------------------------------------------------------------ #


def test_profile_keeps_referrer_per_application():
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    records = [
        {"id": "c1", "job_id": "a", "email": "dana@example.com", "full_name": "דנה",
         "referred_by": "יוסי לוי", "recruitment_status": "נשלח זימון", "created_at": now},
        {"id": "c2", "job_id": "b", "phone": "050-1234567", "email": "DANA@example.com", "full_name": "דנה",
         "referred_by": "מיכל כהן", "created_at": now + timedelta(days=3)},
        {"id": "c3", "job_id": "b", "email": "other@example.com", "full_name": "רון"},
    ]
    pool = [{"id": "p1", "phone": "+972 50 123 4567", "referred_by": "יוסי  לוי",
             "created_at": now - timedelta(days=30)}]
    jobs_by_id = {"a": {"job_title": "מפתח/ת"}, "b": {"job_title": "מנהל/ת מוצר"}}
    people = list_people(records, jobs_by_id, pool_candidates=pool)

    assert [p["full_name"] for p in people] == ["דנה", "רון"]  # most recently active first
    dana = people[0]
    apps = dana["applications"]
    assert [(a["job_title"], a["referred_by"], a["recruitment_status"]) for a in apps] == [
        ("מנהל/ת מוצר", "מיכל כהן", "לא טופל"),  # newest application first; missing status = default
        ("מפתח/ת", "יוסי לוי", "נשלח זימון"),
    ]
    assert dana["talent_pool_entries"][0]["referred_by"] == "יוסי לוי"
    assert dana["referrers"] == ["מיכל כהן", "יוסי לוי"]  # spacing variants count once
    assert dana["last_activity"] == now + timedelta(days=3)
    assert people[1]["referrers"] == [] and people[1]["last_activity"] is None


def test_referrer_suggestions_most_used_first():
    records = [{"referred_by": n} for n in ("מיכל כהן", "יוסי לוי", "יוסי  לוי", " ", "Avi", "avi", "AVI")]
    # Case/spacing variants are one referrer; ties keep the first spelling seen
    assert list_referrers(records) == ["Avi", "יוסי לוי", "מיכל כהן"]
    assert list_referrers([]) == []


# ------------------------------------------------------------------ #
# End to end: routers + FirestoreService                               #
# ------------------------------------------------------------------ #


def test_manual_and_uploaded_candidates_keep_their_referrer():
    _, _, client, job_a, job_b = _setup()

    r = client.post(f"/api/jobs/{job_a}/candidates",
                    json={"full_name": "דנה", "email": "dana@example.com", "referred_by": " יוסי לוי "})
    assert r.status_code == 201 and r.json()["referred_by"] == "יוסי לוי"

    # Upload: one referrer for the whole batch
    r = client.post(f"/api/jobs/{job_b}/candidates/upload",
                    files=[_cv("דנה", "לוי", "dana@example.com", "0501234567"),
                           _cv("רון", "כהן", "ron@example.com", "0527654321")],
                    data={"referred_by": "מיכל כהן"})
    assert r.status_code == 201, r.text
    assert [x["candidate"]["referred_by"] for x in r.json()] == ["מיכל כהן", "מיכל כהן"]

    # Upload without a referrer still works (field is optional)
    r = client.post(f"/api/jobs/{job_a}/candidates/upload", files=[_cv("אבי", "", "avi@example.com", "")])
    assert r.json()[0]["candidate"]["referred_by"] == ""

    listed = {c["full_name"]: c["referred_by"] for c in client.get(f"/api/jobs/{job_b}/candidates").json()}
    assert listed == {"דנה": "מיכל כהן", "רון": "מיכל כהן"}

    # The same person, two jobs, two referrers -> one profile, referrer per application
    dana = _person(client, "dana@example.com")
    by_job = {a["job_id"]: a for a in dana["applications"]}
    assert by_job[job_a]["referred_by"] == "יוסי לוי" and by_job[job_b]["referred_by"] == "מיכל כהן"
    assert by_job[job_a]["job_title"] == "מפתח/ת Python" and by_job[job_a]["created_at"]
    assert set(dana["referrers"]) == {"יוסי לוי", "מיכל כהן"}
    assert len([p for p in client.get("/api/candidates").json() if "dana@example.com" in p["emails"]]) == 1


def test_status_and_referrer_edits_show_in_profile():
    _, _, client, job_a, _ = _setup()
    cid = client.post(f"/api/jobs/{job_a}/candidates", json={"full_name": "דנה", "email": "d@example.com"}).json()["id"]

    client.patch(f"/api/jobs/{job_a}/candidates/{cid}/status", json={"recruitment_status": "גויס/ה"})
    r = client.patch(f"/api/jobs/{job_a}/candidates/{cid}", json={"referred_by": "יוסי  לוי"})
    assert r.json()["referred_by"] == "יוסי לוי"
    app = _person(client, "d@example.com")["applications"][0]
    assert (app["recruitment_status"], app["referred_by"]) == ("גויס/ה", "יוסי לוי")

    assert client.patch(f"/api/jobs/{job_a}/candidates/{cid}", json={"referred_by": ""}).json()["referred_by"] == ""
    assert _person(client, "d@example.com")["referrers"] == []


def test_talent_pool_referrer_and_assignment():
    _, _, client, job_a, job_b = _setup()
    r = client.post("/api/talent-pool", json={"full_name": "שירה", "email": "shira@example.com", "referred_by": "אבי"})
    pool_id = r.json()["id"]
    assert r.json()["referred_by"] == "אבי"

    r = client.post("/api/talent-pool/upload", files=[_cv("נועה", "", "noa@example.com", "")],
                    data={"referred_by": "מיכל כהן"})
    assert r.json()[0]["candidate"]["referred_by"] == "מיכל כהן"

    r = client.patch(f"/api/talent-pool/{pool_id}", json={"referred_by": "אבי לוי"})
    assert r.status_code == 200 and r.json()["referred_by"] == "אבי לוי"
    assert client.patch("/api/talent-pool/nope", json={"referred_by": "x"}).status_code == 404
    assert client.patch(f"/api/talent-pool/{pool_id}", json={}).status_code == 422

    # Assigning from the pool keeps the pool's referrer by default...
    r = client.post(f"/api/jobs/{job_a}/candidates/from-pool/{pool_id}")
    assert r.status_code == 201 and r.json()["referred_by"] == "אבי לוי"
    # ...or records a different referrer for this application
    r = client.post(f"/api/jobs/{job_b}/candidates/from-pool/{pool_id}", json={"referred_by": "דן"})
    assert r.json()["referred_by"] == "דן"

    shira = _person(client, "shira@example.com")
    assert shira["in_talent_pool"] and shira["talent_pool_entries"][0]["referred_by"] == "אבי לוי"
    assert sorted(a["referred_by"] for a in shira["applications"]) == ["אבי לוי", "דן"]

    assert client.get("/api/candidates/referrers").json()[0] == "אבי לוי"  # used twice


def test_people_list_does_not_count_pool_or_jobs_twice():
    """The people list reads job candidates via collection_group('candidates');
    no top-level collection may share that name."""
    fake, _, client, job_a, _ = _setup()
    client.post(f"/api/jobs/{job_a}/candidates", json={"full_name": "דנה", "email": "d@example.com"})
    client.post("/api/talent-pool", json={"full_name": "דנה", "email": "d@example.com"})
    people = client.get("/api/candidates").json()
    assert len(people) == 1 and len(people[0]["applications"]) == 1 and people[0]["in_talent_pool"]
    assert not any(p[0] == "candidates" for p in fake.store)


def test_candidates_excel_has_referrer_column():
    _, _, client, job_a, _ = _setup()
    client.post(f"/api/jobs/{job_a}/candidates", json={"full_name": "דנה", "referred_by": "יוסי לוי"})
    ws = load_workbook(io.BytesIO(client.get(f"/api/jobs/{job_a}/export-excel").content)).active
    headers = [c.value for c in ws[1]]
    assert ws.cell(2, headers.index("הובא על ידי") + 1).value == "יוסי לוי"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
