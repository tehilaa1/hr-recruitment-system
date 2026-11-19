"""Parallel CV ingest, name retry, completion flag, manual entry and pool matching.

No network, Firebase or Gemini access — the AI and DB are stubbed.
Run:  cd backend && python -m pytest tests/      (or: python tests/test_candidate_features.py)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.candidate import (  # noqa: E402
    DEFAULT_STATUS,
    CandidateCreate,
    CandidateResponse,
    CandidateUpdate,
)
from app.services.cv_ingest_service import ingest_cvs  # noqa: E402
from app.services.dedup_service import CandidateDeduplicator, exclude_existing  # noqa: E402
from app.services.gemini_service import (  # noqa: E402
    GeminiParseError,
    GeminiService,
    is_missing_name,
)


# ------------------------------------------------------------------ #
# Stubs                                                                #
# ------------------------------------------------------------------ #


class FakeUpload:
    def __init__(self, filename: str, content: bytes = b"x", content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


class FakeAI:
    """parse_cv_async returns the JSON encoded in the file content after a delay."""

    def __init__(self, delay: float = 0.0, limit: int = 4):
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self._slots = asyncio.Semaphore(limit)

    async def parse_cv_async(self, content: bytes, file_name: str, content_type: str) -> dict:
        async with self._slots:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(self.delay)
                data = json.loads(content)
                if "boom" in data:
                    raise GeminiParseError("שרת ה-AI עמוס כרגע")
                return data
            finally:
                self.active -= 1


def _cv(name: str, **fields) -> FakeUpload:
    return FakeUpload(f"{name}.pdf", json.dumps({"full_name": name, **fields}).encode())


def _save_into(store: list):
    def save(data: dict, cv=None) -> dict:
        # The test CVs are JSON, not a storable file type, so cv is None here
        # (storing real files is covered by tests/test_cv_files.py)
        saved = {"id": f"id{len(store)}", **data, "_cv": cv}
        store.append(saved)
        return saved
    return save


def _ingest(files, ai, existing=(), extra=None):
    store: list = []
    results = asyncio.run(
        ingest_cvs(
            files,
            ai,
            CandidateDeduplicator(list(existing)),
            save=_save_into(store),
            duplicate_message=lambda field, match: f"dup:{field}:{match.get('id')}",
            extra_fields=extra,
        )
    )
    return results, store


def _stub_gemini(responses: list) -> GeminiService:
    """GeminiService without a real client; _call_with_retry pops canned responses."""
    svc = GeminiService.__new__(GeminiService)
    calls: list = []

    def fake_call(contents, file_name, temperature=0.1):
        calls.append(contents)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps(item, ensure_ascii=False)

    svc._call_with_retry = fake_call  # type: ignore[method-assign]
    svc.calls = calls  # type: ignore[attr-defined]
    return svc


_PARSED = {
    "full_name": "", "family_name": "", "phone": "050-1234567", "email": "a@b.com",
    "address": "", "profession": "מהנדסת", "years_of_experience": 3,
}


# ------------------------------------------------------------------ #
# Parallel ingest                                                      #
# ------------------------------------------------------------------ #


def test_ingest_parses_files_concurrently():
    ai = FakeAI(delay=0.2, limit=4)
    files = [_cv(f"p{i}", email=f"p{i}@x.com") for i in range(4)]
    start = time.perf_counter()
    results, store = _ingest(files, ai)
    elapsed = time.perf_counter() - start
    assert all(r["success"] for r in results)
    assert len(store) == 4
    assert ai.max_active == 4
    assert elapsed < 0.6, f"looks sequential: {elapsed:.2f}s for 4 × 0.2s"


def test_ingest_respects_concurrency_limit():
    ai = FakeAI(delay=0.05, limit=2)
    _ingest([_cv(f"p{i}", email=f"p{i}@x.com") for i in range(6)], ai)
    assert ai.max_active == 2


def test_ingest_keeps_upload_order_and_isolates_failures():
    files = [
        _cv("first", email="1@x.com"),
        FakeUpload("notes.txt"),
        FakeUpload("bad.pdf", json.dumps({"boom": 1}).encode()),
        _cv("last", email="2@x.com"),
    ]
    results, store = _ingest(files, FakeAI(), extra={"recruitment_status": DEFAULT_STATUS})
    assert [r["file_name"] for r in results] == ["first.pdf", "notes.txt", "bad.pdf", "last.pdf"]
    assert [r["success"] for r in results] == [True, False, False, True]
    assert ".txt" in results[1]["error"]
    assert "עמוס" in results[2]["error"]
    assert all(s["recruitment_status"] == DEFAULT_STATUS for s in store)
    assert results[0]["candidate"]["file_name"] == "first.pdf"


def test_ingest_dedups_against_existing_and_within_batch():
    existing = [{"id": "old", "email": "old@x.com", "phone": ""}]
    files = [
        _cv("a", email="OLD@x.com "),          # matches existing record
        _cv("b", phone="+972-50-111-2222"),    # new
        _cv("c", phone="050 1112222"),         # same phone as "b", same batch
    ]
    results, store = _ingest(files, FakeAI(), existing=existing)
    assert results[0]["duplicate"] and results[0]["duplicate_of_id"] == "old"
    assert results[1]["success"]
    assert results[2]["duplicate"]
    assert results[2]["duplicate_of_id"] == results[1]["candidate"]["id"]
    assert len(store) == 1


def test_gemini_parse_cv_async_runs_in_threads_with_a_cap():
    import threading

    svc = GeminiService.__new__(GeminiService)
    lock = threading.Lock()
    state = {"active": 0, "max": 0}

    def slow_parse(file_bytes, file_name, content_type):
        with lock:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
        time.sleep(0.1)  # blocking, like the real Gemini call
        with lock:
            state["active"] -= 1
        return {"full_name": file_name}

    svc.parse_cv = slow_parse  # type: ignore[method-assign]

    async def run():
        svc._parse_slots = asyncio.Semaphore(3)
        return await asyncio.gather(
            *(svc.parse_cv_async(b"", f"f{i}", "application/pdf") for i in range(9))
        )

    start = time.perf_counter()
    results = asyncio.run(run())
    elapsed = time.perf_counter() - start
    assert [r["full_name"] for r in results] == [f"f{i}" for i in range(9)]
    assert state["max"] == 3
    assert elapsed < 0.6, f"9 × 0.1s with 3 slots took {elapsed:.2f}s"


# ------------------------------------------------------------------ #
# Name retry                                                           #
# ------------------------------------------------------------------ #


def test_placeholder_names_are_missing():
    for value in ("", "  ", None, "לא ידוע", "לא צוין", "Unknown", "N/A", '"לא ידוע"', "-"):
        assert is_missing_name(value), value
    for value in ("דנה", "Dana", "אבי לוי"):
        assert not is_missing_name(value), value


def test_name_retry_fills_missing_name():
    svc = _stub_gemini([
        {**_PARSED, "full_name": "לא ידוע"},
        {"full_name": "דנה", "family_name": "לוי"},
    ])
    result = svc.parse_cv(b"%PDF", "cv.pdf", "application/pdf")
    assert (result["full_name"], result["family_name"]) == ("דנה", "לוי")
    assert result["email"] == "a@b.com"
    assert len(svc.calls) == 2
    assert "ONLY on finding the name" in svc.calls[1][-1]


def test_no_retry_when_name_present():
    svc = _stub_gemini([{**_PARSED, "full_name": "Dana", "family_name": "Levi"}])
    assert svc.parse_cv(b"%PDF", "cv.pdf", "application/pdf")["full_name"] == "Dana"
    assert len(svc.calls) == 1


def test_failed_name_retry_keeps_parse_and_drops_placeholder():
    svc = _stub_gemini([
        {**_PARSED, "full_name": "לא צוין", "family_name": "לא ידוע"},
        GeminiParseError("overloaded"),
    ])
    result = svc.parse_cv(b"%PDF", "cv.pdf", "application/pdf")
    assert result["full_name"] == "" and result["family_name"] == ""
    assert result["profession"] == "מהנדסת"


# ------------------------------------------------------------------ #
# Completion flag & manual entry                                       #
# ------------------------------------------------------------------ #


def test_legacy_records_default_to_not_completed():
    legacy = {
        "id": "c1", "job_id": "j1", "recruitment_status": DEFAULT_STATUS,
        "file_name": "cv.pdf", "created_at": "2026-01-01T00:00:00Z",
    }
    assert CandidateResponse(**legacy).is_completed is False


def test_update_model_accepts_completion():
    assert CandidateUpdate(is_completed=True).model_dump(exclude_none=True) == {"is_completed": True}


def test_manual_candidate_requires_name_and_defaults_status():
    created = CandidateCreate(full_name="  רון ", phone=" 050-1 ")
    assert created.full_name == "רון" and created.phone == "050-1"
    assert created.recruitment_status == DEFAULT_STATUS
    for bad in ({"full_name": "   "}, {"full_name": "x", "recruitment_status": "hired"}):
        try:
            CandidateCreate(**bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid payload {bad}")


# ------------------------------------------------------------------ #
# Pool matching                                                        #
# ------------------------------------------------------------------ #


def test_exclude_existing_by_normalized_email_or_phone():
    pool = [
        {"id": "p1", "email": "Dana@X.com", "phone": ""},
        {"id": "p2", "email": "", "phone": "+972 52-000-0000"},
        {"id": "p3", "email": "new@x.com", "phone": "053-9999999"},
    ]
    applied = [{"email": "dana@x.com"}, {"phone": "0520000000"}]
    assert [c["id"] for c in exclude_existing(pool, applied)] == ["p3"]


def test_match_candidates_drops_unknown_ids_and_sorts():
    svc = _stub_gemini([{"matches": [
        {"id": "p1", "score": 60, "match_reason": "ניסיון רלוונטי"},
        {"id": "ghost", "score": 99, "match_reason": "לא קיים"},
        {"id": "p2", "score": 90, "match_reason": "מתאים מאוד"},
        {"id": "p2", "score": 10, "match_reason": "כפול"},
        {"id": "p3", "score": 80, "match_reason": ""},
    ]}])
    pool = [{"id": f"p{i}", "full_name": f"n{i}"} for i in (1, 2, 3)]
    result = svc.match_candidates("מפתח", "", pool, limit=5)
    assert [(m["id"], m["score"]) for m in result] == [("p2", 90), ("p1", 60)]
    assert svc.match_candidates("מפתח", "", [], limit=5) == []


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
