"""Original CV files kept with candidates, and the per-record profile lookup.

Runs the real routers + FirestoreService on an in-memory Firestore stand-in,
with a stub CV parser instead of Gemini.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_cv_files.py)
"""
from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.dependencies import get_firestore_service, get_gemini_service  # noqa: E402
from app.routers import candidates, jobs, search, talent_pool  # noqa: E402
from app.services import invoice_service  # noqa: E402
from app.services.cv_file_service import (  # noqa: E402
    CV_MAX_BYTES,
    DOCX,
    build_cv_file,
    detect_cv_content_type,
)
from fake_firestore import TENANT, fake_service, sign_in  # noqa: E402

# Larger than one chunk, so reassembly of several chunks is exercised
PDF_BYTES = b"%PDF-1.4\n" + bytes(range(256)) * 4000  # ~1 MB


class _StubAI:
    """parse_cv_async returns the person encoded in the file name: "first|email.ext"."""

    async def parse_cv_async(self, content, file_name, content_type):
        first, email = file_name.rsplit(".", 1)[0].split("|")
        return {"full_name": first, "family_name": "", "email": email, "phone": "",
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
    job = client.post("/api/jobs", json={"job_title": "מפתח/ת", "description": "x", "interview_type": "יחידני"}).json()["id"]
    return fake, client, job


def _file(name, content=PDF_BYTES, ctype="application/pdf"):
    return ("files", (name, io.BytesIO(content), ctype))


def _cv_chunks(fake):
    return [p for p in fake.store if "cv_chunks" in p]


# ------------------------------------------------------------------ #
# Pure helpers                                                         #
# ------------------------------------------------------------------ #


def test_content_type_is_sniffed_not_trusted():
    assert detect_cv_content_type(b"%PDF-1.7 ...", "x.png") == "application/pdf"
    assert detect_cv_content_type(b"\x89PNG\r\n\x1a\n...", "x.pdf") == "image/png"
    assert detect_cv_content_type(b"\xff\xd8\xff\xe0", "x") == "image/jpeg"
    assert detect_cv_content_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ", "x.webp") == "image/webp"
    assert detect_cv_content_type(b"PK\x03\x04...", "cv.docx") == DOCX
    assert detect_cv_content_type(b"PK\x03\x04...", "cv.zip") is None  # any other ZIP
    assert detect_cv_content_type(b"<html><script>", "cv.pdf") is None


def test_build_cv_file_limits_and_safe_name():
    assert build_cv_file("a.pdf", b"") is None
    assert build_cv_file("a.pdf", b"%PDF-" + b"0" * CV_MAX_BYTES) is None
    cv = build_cv_file("../../קורות חיים\x00 דנה.PDF", b"%PDF-1.4")
    assert cv.meta == {"file_name": "קורות חיים דנה.pdf", "content_type": "application/pdf", "size": 8}


def test_inline_disposition_fallback_stem():
    assert 'filename="cv.pdf"' in invoice_service.inline_disposition("קורות.pdf", "cv")
    assert 'filename="invoice.pdf"' in invoice_service.inline_disposition("חשבונית.pdf")


# ------------------------------------------------------------------ #
# Upload → stored → served                                             #
# ------------------------------------------------------------------ #


def test_uploaded_job_cv_is_stored_and_served():
    fake, client, job = _setup()
    r = client.post(f"/api/jobs/{job}/candidates/upload", files=[_file("דנה|d@x.com.pdf")])
    cand = r.json()[0]["candidate"]
    assert cand["cv_file"] == {"file_name": "דנה|d@x.com.pdf", "content_type": "application/pdf", "size": len(PDF_BYTES)}
    assert len(_cv_chunks(fake)) == 2

    r = client.get(f"/api/jobs/{job}/candidates/{cand['id']}/cv")
    assert r.status_code == 200 and r.content == PDF_BYTES
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline;")
    assert r.headers["x-content-type-options"] == "nosniff"

    # Visible in the list, the person profile, and the global people list
    assert client.get(f"/api/jobs/{job}/candidates").json()[0]["cv_file"]["size"] == len(PDF_BYTES)
    person = client.get("/api/candidates").json()[0]
    assert person["applications"][0]["cv_file"]["content_type"] == "application/pdf"

    # Job candidates live in a collection named "candidates"; the chunks must not
    # be picked up by the collection-group query as extra people
    assert len(client.get("/api/candidates").json()) == 1


def test_unstorable_upload_is_still_parsed_without_a_file():
    fake, client, _ = _setup()
    r = client.post("/api/talent-pool/upload", files=[_file("נועה|n@x.com.pdf", b"not really a pdf")])
    assert r.json()[0]["success"] and r.json()[0]["candidate"]["cv_file"] is None
    assert not _cv_chunks(fake)
    pool_id = r.json()[0]["candidate"]["id"]
    r = client.get(f"/api/talent-pool/{pool_id}/cv")
    assert r.status_code == 404 and "קורות חיים" in r.json()["detail"]


def test_manual_and_legacy_records_have_no_cv():
    fake, client, job = _setup()
    pool = client.post("/api/talent-pool", json={"full_name": "שירה"}).json()
    assert pool["cv_file"] is None
    assert client.get(f"/api/talent-pool/{pool['id']}/cv").status_code == 404
    # A record from before CV files were kept: file_name only
    fake.store[("talent_pool", "legacy")] = {"owner_id": TENANT, "full_name": "ותיק", "file_name": "old.pdf", "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    legacy = next(c for c in client.get("/api/talent-pool").json() if c["id"] == "legacy")
    assert legacy["file_name"] == "old.pdf" and legacy["cv_file"] is None


def test_assign_from_pool_copies_the_cv():
    fake, client, job = _setup()
    pool_id = client.post("/api/talent-pool/upload", files=[_file("רון|r@x.com.pdf")]).json()[0]["candidate"]["id"]
    r = client.post(f"/api/jobs/{job}/candidates/from-pool/{pool_id}")
    assert r.status_code == 201 and r.json()["cv_file"]["size"] == len(PDF_BYTES)
    assert client.get(f"/api/jobs/{job}/candidates/{r.json()['id']}/cv").content == PDF_BYTES

    # Deleting the pool entry keeps the job's own copy
    assert client.delete(f"/api/talent-pool/{pool_id}").status_code == 204
    assert client.get(f"/api/jobs/{job}/candidates/{r.json()['id']}/cv").content == PDF_BYTES
    assert not any(p[0] == "talent_pool" for p in _cv_chunks(fake))


def test_attach_and_replace_cv_on_existing_records():
    fake, client, job = _setup()
    cand = client.post(f"/api/jobs/{job}/candidates", json={"full_name": "דנה"}).json()
    assert cand["cv_file"] is None

    r = client.put(f"/api/jobs/{job}/candidates/{cand['id']}/cv", files={"file": ("cv.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    assert r.status_code == 200 and r.json()["cv_file"]["size"] == len(PDF_BYTES)
    assert len(_cv_chunks(fake)) == 2

    # A shorter replacement leaves no stale chunks behind
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 10
    r = client.put(f"/api/jobs/{job}/candidates/{cand['id']}/cv", files={"file": ("photo.jpg", io.BytesIO(png), "image/jpeg")})
    assert r.json()["cv_file"] == {"file_name": "photo.png", "content_type": "image/png", "size": len(png)}
    assert len(_cv_chunks(fake)) == 1
    assert client.get(f"/api/jobs/{job}/candidates/{cand['id']}/cv").content == png

    bad = client.put(f"/api/jobs/{job}/candidates/{cand['id']}/cv", files={"file": ("x.pdf", io.BytesIO(b"<html>"), "application/pdf")})
    assert bad.status_code == 415
    assert client.put(f"/api/jobs/{job}/candidates/nope/cv", files={"file": ("cv.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}).status_code == 404

    pool = client.post("/api/talent-pool", json={"full_name": "שירה"}).json()
    r = client.put(f"/api/talent-pool/{pool['id']}/cv", files={"file": ("cv.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    assert r.status_code == 200 and client.get(f"/api/talent-pool/{pool['id']}/cv").content == PDF_BYTES


def test_deleting_candidate_or_job_removes_its_cv():
    fake, client, job = _setup()
    a = client.post(f"/api/jobs/{job}/candidates/upload", files=[_file("א|a@x.com.pdf")]).json()[0]["candidate"]
    client.post(f"/api/jobs/{job}/candidates/upload", files=[_file("ב|b@x.com.pdf")])
    assert len(_cv_chunks(fake)) == 4
    assert client.delete(f"/api/jobs/{job}/candidates/{a['id']}").status_code == 204
    assert len(_cv_chunks(fake)) == 2
    assert client.delete(f"/api/jobs/{job}").status_code in (200, 204)
    assert not _cv_chunks(fake)


# ------------------------------------------------------------------ #
# Profile of one person by any of their record ids                    #
# ------------------------------------------------------------------ #


def test_person_by_record_merges_pool_and_applications():
    _, client, job = _setup()
    pool_id = client.post("/api/talent-pool/upload", files=[_file("רון|r@x.com.pdf")]).json()[0]["candidate"]["id"]
    app_id = client.post(f"/api/jobs/{job}/candidates/from-pool/{pool_id}").json()["id"]

    by_pool = client.get(f"/api/candidates/by-record/{pool_id}").json()
    by_app = client.get(f"/api/candidates/by-record/{app_id}").json()
    assert by_pool == by_app
    assert by_pool["in_talent_pool"] and len(by_pool["applications"]) == 1
    assert by_pool["talent_pool_entries"][0]["cv_file"]["size"] == len(PDF_BYTES)

    assert client.get("/api/candidates/by-record/nope").status_code == 404
    # The fixed routes still win over /by-record/... and /{...}
    assert client.get("/api/candidates/referrers").status_code == 200


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
