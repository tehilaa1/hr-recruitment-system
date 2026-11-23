"""Multi-tenant isolation and the public demo workspace.

Runs the real app (app.main.app: every router, the real get_current_user and
role checks) on an in-memory Firestore. Only Firebase itself is stubbed:
a bearer token "tok:<email>" verifies as that email, and the users/{email}
documents (with their tenant_id) decide everything else.

Workspaces: A and B (two real customers) and the demo workspace.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_tenant_isolation.py)
"""
from __future__ import annotations

import io
import sys
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.dependencies import get_firestore_service, get_gemini_service, get_password_reset_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth_service, demo_limits  # noqa: E402
from app.services.demo_seed import JOBS, PEOPLE, POOL, reset_demo, seed_demo  # noqa: E402
from app.services.firestore_service import check_owner_id  # noqa: E402
from app.services.password_reset_service import PasswordResetService  # noqa: E402
from fake_firestore import fake_service  # noqa: E402

A, B = "tenant-a", "tenant-b"
DEMO = get_settings().DEMO_TENANT_ID
PDF = b"%PDF-1.4\n" + b"x" * 500
JOB = {"job_title": "מפתח/ת", "description": "Python", "interview_type": "יחידני"}


class _StubAI:
    def __init__(self):
        self.seen_pool_ids: list[str] = []

    async def parse_cv_async(self, content, file_name, content_type):
        first, email = file_name.rsplit(".", 1)[0].split("|")
        return {"full_name": first, "family_name": "", "email": email, "phone": "",
                "address": "", "profession": "", "years_of_experience": 0}

    def match_candidates(self, title, description, candidates, limit=5):
        self.seen_pool_ids = [c["id"] for c in candidates]
        return [{"id": c["id"], "score": 80, "match_reason": "מתאים"} for c in candidates[:limit]]


class World:
    """One shared database, and a client per signed-in user."""

    def __init__(self):
        self.fake, self.db = fake_service()
        self.ai = _StubAI()
        app.dependency_overrides.clear()
        app.dependency_overrides[get_firestore_service] = lambda: self.db
        app.dependency_overrides[get_gemini_service] = lambda: self.ai
        auth_service.verify_id_token = self._verify
        auth_service.get_or_create_account = lambda email, name="", password=None: (f"uid-{email}", True)
        auth_service.delete_account = lambda uid: None
        demo_limits.demo_ai_counter.reset()

        self.add_user("admin@a.com", A, "admin")
        self.add_user("editor@a.com", A, "editor")
        self.add_user("admin@b.com", B, "admin")
        self.add_user("demo@demo.com", DEMO, "editor")
        self.add_user("boss@a.com", A, "admin", is_super_admin=True)

    @staticmethod
    def _verify(token: str) -> dict:
        if not token.startswith("tok:"):
            raise auth_service.InvalidTokenError("bad token")
        email = token[4:]
        return {"uid": f"uid-{email}", "email": email}

    def add_user(self, email, tenant, role, **extra):
        data = {"role": role, "uid": f"uid-{email}", "display_name": email, **extra}
        if tenant is not None:
            data["tenant_id"] = tenant
        self.db.set_user(email, data)

    def client(self, email: str) -> TestClient:
        return TestClient(app, headers={"Authorization": f"Bearer tok:{email}"})


def _populate(w: World, email: str, tag: str) -> dict:
    """A job with a candidate (with CV), a pool entry (with CV), a maternity record,
    a 2026 budget with an event, an expense and an invoice. Returns their ids/urls."""
    c = w.client(email)
    job = c.post("/api/jobs", json={**JOB, "job_title": f"משרה {tag}"}).json()["id"]
    up = c.post(f"/api/jobs/{job}/candidates/upload",
                files=[("files", (f"{tag}|{tag}@x.com.pdf", io.BytesIO(PDF), "application/pdf"))]).json()
    cand = up[0]["candidate"]["id"]
    pool = c.post("/api/talent-pool/upload",
                  files=[("files", (f"{tag}pool|{tag}pool@x.com.pdf", io.BytesIO(PDF), "application/pdf"))]
                  ).json()[0]["candidate"]["id"]
    mat = c.post("/api/maternity", json={"name": f"יולדת {tag}"}).json()["id"]
    assert c.post("/api/budgets", json={"year": 2026, "total_budget": 1000}).status_code == 201
    event = c.post("/api/budgets/2026/events", json={"name": f"חג {tag}", "allocated_budget": 500}).json()["id"]
    expense = c.post(f"/api/budgets/2026/events/{event}/expenses",
                     json={"item_name": f"פריט {tag}", "total_price": 100}).json()["id"]
    invoice = f"/api/budgets/2026/events/{event}/expenses/{expense}/invoice"
    assert c.put(invoice, files={"file": ("i.pdf", io.BytesIO(PDF), "application/pdf")}).status_code == 200
    c.put("/api/maternity/settings", json={"notify_recipients": [f"{tag}@x.com"]})
    return {"job": job, "cand": cand, "pool": pool, "mat": mat, "event": event,
            "expense": expense, "invoice": invoice, "name": tag}


def _setup():
    w = World()
    return w, _populate(w, "admin@a.com", "alpha"), _populate(w, "admin@b.com", "beta")


# ------------------------------------------------------------------ #
# Authentication → workspace                                           #
# ------------------------------------------------------------------ #


def test_unauthenticated_and_unassigned_users_are_rejected():
    w = World()
    assert TestClient(app).get("/api/jobs").status_code == 401
    assert w.client("nobody@x.com").get("/api/jobs").status_code == 403  # no users/ doc
    w.add_user("legacy@a.com", None, "admin")  # not migrated: no tenant_id
    assert w.client("legacy@a.com").get("/api/jobs").status_code == 403
    w.add_user("weird@a.com", "", "admin")
    assert w.client("weird@a.com").get("/api/jobs").status_code == 403


def test_tenant_id_validation():
    for bad in (None, "", "a/b", "a__b", "x" * 65, 5):
        try:
            check_owner_id(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} accepted")
    assert check_owner_id("AbC-123") == "AbC-123"


def test_team_members_share_their_workspace():
    w, a, _ = _setup()
    jobs = w.client("editor@a.com").get("/api/jobs").json()
    assert [j["id"] for j in jobs] == [a["job"]]


# ------------------------------------------------------------------ #
# A can't read or change B's records                                   #
# ------------------------------------------------------------------ #


def test_jobs_and_candidates_are_isolated():
    w, a, b = _setup()
    ca = w.client("admin@a.com")
    assert [j["id"] for j in ca.get("/api/jobs").json()] == [a["job"]]

    job, cand = f"/api/jobs/{b['job']}", f"/api/jobs/{b['job']}/candidates/{b['cand']}"
    requests = [
        ca.get(job), ca.put(job, json={"job_title": "נגנב"}), ca.get(f"{job}/export-excel"),
        ca.post(f"{job}/match-pool"),
        ca.get(f"{job}/candidates"), ca.post(f"{job}/candidates", json={"full_name": "זר"}),
        ca.post(f"{job}/candidates/upload", files=[("files", ("x|x@x.com.pdf", io.BytesIO(PDF), "application/pdf"))]),
        ca.get(cand), ca.patch(cand, json={"full_name": "נגנב"}),
        ca.patch(f"{cand}/status", json={"recruitment_status": "שלילי"}),
        ca.patch(f"{cand}/complete", json={"is_completed": True}),
        ca.get(f"{cand}/cv"), ca.put(f"{cand}/cv", files={"file": ("cv.pdf", io.BytesIO(PDF), "application/pdf")}),
        ca.post(f"/api/jobs/{a['job']}/candidates/from-pool/{b['pool']}"),
        ca.delete(cand), ca.delete(job),
    ]
    assert [r.status_code for r in requests] == [404] * len(requests), [r.status_code for r in requests]

    # B's data is untouched
    cb = w.client("admin@b.com")
    assert cb.get(job).json()["job_title"] == "משרה beta"
    got = cb.get(cand).json()
    assert got["full_name"] == "beta" and got["recruitment_status"] == "לא טופל"
    assert cb.get(f"{cand}/cv").content == PDF
    assert len(cb.get(f"{job}/candidates").json()) == 1


def test_candidate_of_another_tenant_under_my_job_is_invisible():
    """Even a record planted under A's job (path guess) is hidden unless it is A's."""
    w, a, b = _setup()
    w.fake.store[("jobs", a["job"], "candidates", "planted")] = {"full_name": "זר", "owner_id": B}
    ca = w.client("admin@a.com")
    assert ca.get(f"/api/jobs/{a['job']}/candidates/planted").status_code == 404
    assert "זר" not in str(ca.get(f"/api/jobs/{a['job']}/candidates").json())
    assert "זר" not in str(ca.get("/api/candidates").json())


def test_talent_pool_and_global_search_are_isolated():
    w, a, b = _setup()
    ca = w.client("admin@a.com")
    assert [p["id"] for p in ca.get("/api/talent-pool").json()] == [a["pool"]]
    pool = f"/api/talent-pool/{b['pool']}"
    codes = [ca.patch(pool, json={"referred_by": "x"}).status_code, ca.get(f"{pool}/cv").status_code,
             ca.put(f"{pool}/cv", files={"file": ("cv.pdf", io.BytesIO(PDF), "application/pdf")}).status_code,
             ca.delete(pool).status_code]
    assert codes == [404] * 4

    people = ca.get("/api/candidates").json()
    assert "beta" not in str(people) and "alpha" in str(people)
    assert ca.get("/api/candidates/search", params={"q": "beta"}).json() == []
    assert ca.get(f"/api/candidates/by-record/{b['cand']}").status_code == 404
    assert ca.get(f"/api/candidates/by-record/{b['pool']}").status_code == 404
    assert w.client("admin@b.com").get(pool + "/cv").content == PDF


def test_ai_matching_only_sees_own_pool():
    w, a, b = _setup()
    assert w.client("admin@a.com").post(f"/api/jobs/{a['job']}/match-pool").status_code == 200
    assert w.ai.seen_pool_ids == [a["pool"]]


def test_maternity_records_and_settings_are_isolated():
    w, a, b = _setup()
    ca, cb = w.client("admin@a.com"), w.client("admin@b.com")
    assert [r["id"] for r in ca.get("/api/maternity").json()] == [a["mat"]]
    rec = f"/api/maternity/{b['mat']}"
    assert ca.patch(rec, json={"name": "נגנב"}).status_code == 404
    assert ca.delete(rec).status_code == 404
    assert "beta" not in ca.get("/api/maternity/export-excel").content.decode("latin-1")
    assert ca.get("/api/maternity/settings").json()["notify_recipients"] == ["alpha@x.com"]
    assert cb.get("/api/maternity/settings").json()["notify_recipients"] == ["beta@x.com"]
    assert [r["name"] for r in cb.get("/api/maternity").json()] == ["יולדת beta"]


def test_budgets_with_same_year_are_isolated():
    w, a, b = _setup()
    ca, cb = w.client("admin@a.com"), w.client("admin@b.com")
    year_a = ca.get("/api/budgets/2026").json()
    assert [e["name"] for e in year_a["events"]] == ["חג alpha"]

    ev = f"/api/budgets/2026/events/{b['event']}"
    exp = f"{ev}/expenses/{b['expense']}"
    requests = [
        ca.patch(ev, json={"name": "נגנב"}), ca.get(f"{ev}/expenses"),
        ca.post(f"{ev}/expenses", json={"item_name": "x", "total_price": 1}),
        ca.patch(exp, json={"item_name": "x"}), ca.get(b["invoice"]),
        ca.put(b["invoice"], files={"file": ("i.pdf", io.BytesIO(PDF), "application/pdf")}),
        ca.delete(b["invoice"]), ca.get(f"{ev}/export-excel"), ca.delete(exp), ca.delete(ev),
    ]
    assert [r.status_code for r in requests] == [404] * len(requests), [r.status_code for r in requests]

    # Deleting A's 2026 budget leaves B's 2026 budget (and its invoice) intact
    assert ca.delete("/api/budgets/2026").status_code == 204
    assert ca.get("/api/budgets").json() == []
    assert cb.get("/api/budgets/2026").json()["events"][0]["name"] == "חג beta"
    assert cb.get(b["invoice"]).content == PDF


def test_legacy_records_without_owner_are_invisible():
    w = World()
    w.fake.store[("jobs", "old")] = {"job_title": "ישן", "description": "", "interview_type": "יחידני"}
    w.fake.store[("talent_pool", "old")] = {"full_name": "ישן"}
    w.fake.store[("maternity_leaves", "old")] = {"name": "ישנה"}
    ca = w.client("admin@a.com")
    assert ca.get("/api/jobs").json() == [] and ca.get("/api/jobs/old").status_code == 404
    assert ca.get("/api/talent-pool").json() == [] and ca.get("/api/maternity").json() == []


def test_owner_can_not_be_changed_by_update():
    w, a, _ = _setup()
    assert w.db.update_job(A, a["job"], {"job_title": "x", "owner_id": B})["owner_id"] == A
    assert w.db.get_job(B, a["job"]) is None


# ------------------------------------------------------------------ #
# User management stays inside the workspace                           #
# ------------------------------------------------------------------ #


def test_workspace_admin_manages_only_own_team():
    w = World()
    ca = w.client("admin@a.com")
    emails = {u["email"] for u in ca.get("/api/users").json()}
    assert emails == {"admin@a.com", "editor@a.com", "boss@a.com"}

    # tenant_id in the request is ignored: new users always join the admin's workspace
    r = ca.post("/api/users", json={"email": "new@a.com", "role": "editor", "tenant_id": B})
    assert r.status_code == 201 and r.json()["user"]["tenant_id"] == A
    assert w.db.get_user("new@a.com")["tenant_id"] == A
    assert "new@a.com" not in str(w.client("admin@b.com").get("/api/users").json())

    # Users of another workspace look like missing users
    assert ca.patch("/api/users/admin@b.com", json={"role": "editor"}).status_code == 404
    assert ca.delete("/api/users/admin@b.com").status_code == 404
    assert w.db.get_user("admin@b.com")["role"] == "admin"
    # ... and their email can't be re-registered into A
    assert ca.post("/api/users", json={"email": "admin@b.com"}).status_code == 409


def test_admins_are_counted_per_workspace():
    w = World()
    assert (w.db.count_admins(A), w.db.count_admins(B), w.db.count_admins(DEMO)) == (2, 1, 0)
    w.add_user("second@b.com", B, "admin")
    cb = w.client("second@b.com")
    assert cb.delete("/api/users/admin@b.com").status_code == 204
    assert w.db.count_admins(B) == 1 and w.db.count_admins(A) == 2


def test_me_reports_workspace_and_flags():
    w = World()
    me = w.client("boss@a.com").get("/api/auth/me").json()
    assert (me["tenant_id"], me["is_super_admin"], me["is_demo"]) == (A, True, False)
    me = w.client("demo@demo.com").get("/api/auth/me").json()
    assert (me["tenant_id"], me["is_super_admin"], me["is_demo"]) == (DEMO, False, True)


# ------------------------------------------------------------------ #
# Super admin                                                          #
# ------------------------------------------------------------------ #


def test_only_super_admin_creates_workspaces():
    w = World()
    body = {"name": "Acme", "tenant_id": "acme", "admin_email": "owner@acme.com"}
    assert w.client("admin@a.com").post("/api/admin/tenants", json=body).status_code == 403
    assert w.client("demo@demo.com").post("/api/admin/tenants", json=body).status_code == 403

    boss = w.client("boss@a.com")
    r = boss.post("/api/admin/tenants", json=body)
    assert r.status_code == 201, r.text
    assert w.db.get_user("owner@acme.com")["tenant_id"] == "acme"
    assert boss.post("/api/admin/tenants", json=body).status_code == 409
    assert boss.post("/api/admin/tenants", json={**body, "tenant_id": DEMO, "admin_email": "x@x.com"}).status_code == 409
    assert boss.post("/api/admin/tenants", json={**body, "tenant_id": "a/b"}).status_code == 422

    # The new workspace starts empty, and the super admin still only sees A's data
    owner = w.client("owner@acme.com")
    assert owner.get("/api/jobs").json() == []
    owner.post("/api/jobs", json=JOB)
    assert boss.get("/api/jobs").json() == []


# ------------------------------------------------------------------ #
# Demo workspace                                                       #
# ------------------------------------------------------------------ #


def test_demo_seed_is_complete_idempotent_and_scoped():
    w, a, b = _setup()
    before = {p: v for p, v in w.fake.store.items()}
    counts = seed_demo(w.db, DEMO, today=date(2026, 6, 1))
    assert counts["jobs"] == len(JOBS) and counts["talent_pool"] == len(POOL)
    assert counts["candidates"] == sum(len(apps) for _, apps in JOBS)
    assert seed_demo(w.db, DEMO) == {}  # second run: nothing added

    # Nothing outside the demo workspace changed
    for path, data in before.items():
        assert w.fake.store[path] == data, path

    demo = w.client("demo@demo.com")
    jobs = demo.get("/api/jobs").json()
    assert len(jobs) == len(JOBS)
    assert "alpha" not in str(demo.get("/api/candidates").json())
    # Every seeded application has a downloadable PDF CV
    job = jobs[0]["id"]
    cands = demo.get(f"/api/jobs/{job}/candidates").json()
    cv = demo.get(f"/api/jobs/{job}/candidates/{cands[0]['id']}/cv")
    assert cv.status_code == 200 and cv.content.startswith(b"%PDF")
    assert len(PEOPLE) >= 12 and all(c["cv_file"] for c in cands)
    assert len(demo.get("/api/budgets").json()) == 2
    assert len(demo.get("/api/maternity").json()) == 4
    # ... and A still can't see any of it
    assert [j["id"] for j in w.client("admin@a.com").get("/api/jobs").json()] == [a["job"]]


def test_demo_reset_touches_only_the_demo():
    w, a, b = _setup()
    non_demo = dict(w.fake.store)  # A, B and the users, before the demo exists
    seed_demo(w.db, DEMO)
    demo = w.client("demo@demo.com")
    demo.post("/api/jobs", json={**JOB, "job_title": "נוסף בהדגמה"})

    try:
        reset_demo(w.db, A, DEMO)
    except ValueError:
        pass
    else:
        raise AssertionError("reset of a real workspace must be refused")

    assert w.client("admin@a.com").post("/api/admin/demo/reset").status_code == 403  # not super admin
    r = w.client("boss@a.com").post("/api/admin/demo/reset")
    assert r.status_code == 200, r.text
    assert "נוסף בהדגמה" not in str(demo.get("/api/jobs").json())
    assert len(demo.get("/api/jobs").json()) == len(JOBS)
    for path, data in non_demo.items():
        assert w.fake.store.get(path) == data, path


def test_demo_quotas():
    w = World()
    demo = w.client("demo@demo.com")
    job = demo.post("/api/jobs", json=JOB).json()["id"]
    upload = f"/api/jobs/{job}/candidates/upload"

    def files(n, size=len(PDF)):
        body = b"%PDF-1.4\n" + b"x" * size
        return [("files", (f"p{i}|p{i}@x.com.pdf", io.BytesIO(body), "application/pdf")) for i in range(n)]

    settings = get_settings()
    too_many = demo.post(upload, files=files(settings.DEMO_MAX_FILES_PER_UPLOAD + 1))
    assert too_many.status_code == 413
    assert demo.post(upload, files=files(1, settings.DEMO_MAX_UPLOAD_BYTES + 1)).status_code == 413

    # Daily AI budget: uploads (one call per file) and pool matching share it
    demo_limits.demo_ai_counter.reset()
    demo_limits.demo_ai_counter.consume(settings.DEMO_AI_DAILY_LIMIT - 1, settings.DEMO_AI_DAILY_LIMIT)
    assert demo.post(upload, files=files(1)).status_code == 201
    r = demo.post(upload, files=files(1)[0:1])
    assert r.status_code == 429 and "מכסת" in r.json()["detail"]
    w.db.create_pool_candidate(DEMO, {"full_name": "במאגר"})
    assert demo.post(f"/api/jobs/{job}/match-pool").status_code == 429

    # Real workspaces are never limited
    ca = w.client("admin@a.com")
    job_a = ca.post("/api/jobs", json=JOB).json()["id"]
    r = ca.post(f"/api/jobs/{job_a}/candidates/upload", files=files(settings.DEMO_MAX_FILES_PER_UPLOAD + 1))
    assert r.status_code == 201


def test_demo_record_cap():
    w = World()
    demo = w.client("demo@demo.com")
    cap = get_settings().DEMO_MAX_RECORDS
    for i in range(cap):
        w.db.create_maternity_leave(DEMO, {"name": f"r{i}"})
    assert demo.post("/api/maternity", json={"name": "עוד"}).status_code == 403
    assert w.client("admin@a.com").post("/api/maternity", json={"name": "עוד"}).status_code == 201


def test_demo_account_can_not_manage_users_or_reset_password():
    w = World()
    w.add_user("demo@demo.com", DEMO, "admin", phone="+972501234567")  # even if misconfigured as admin
    demo = w.client("demo@demo.com")
    assert demo.get("/api/users").status_code == 403
    assert demo.post("/api/users", json={"email": "x@x.com"}).status_code == 403

    class _Sms:
        name = "test"
        sent = []

        def send(self, phone, text):
            self.sent.append(phone)

    sms = _Sms()
    resets = PasswordResetService(store=w.db, sms=sms, set_password=lambda uid, pw: None,
                                  locked_tenant_ids=(DEMO,))
    app.dependency_overrides[get_password_reset_service] = lambda: resets
    r = TestClient(app).post("/api/auth/password-reset/request", json={"email": "demo@demo.com"})
    assert r.status_code == 202 and sms.sent == []  # same answer as for anyone, nothing sent
    w.add_user("admin@a.com", A, "admin", phone="+972501234568")
    TestClient(app).post("/api/auth/password-reset/request", json={"email": "admin@a.com"})
    assert sms.sent == ["+972501234568"]


# ------------------------------------------------------------------ #
# Migration of pre multi-tenant data (scripts/migrate_owner_ids.py)    #
# ------------------------------------------------------------------ #


def test_migration_assigns_legacy_data_without_losing_anything():
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    import contextlib
    import migrate_owner_ids as m

    w = World()
    me = "uid-me"  # the workspace id (main() uses the account's Firebase uid)
    store = w.fake.store
    old = datetime(2025, 1, 1, tzinfo=timezone.utc)
    store[("jobs", "j1")] = {**JOB, "job_title": "ישנה", "interviewers": [], "interview_location": "",
                             "interviewer_emails": [], "created_at": old}
    store[("jobs", "j1", "candidates", "c1")] = {
        "full_name": "ותיק", "created_at": old,
        "cv_file": {"file_name": "cv.pdf", "content_type": "application/pdf", "size": len(PDF)},
    }
    store[("jobs", "j1", "candidates", "c1", "cv_chunks", "0000")] = {"index": 0, "data": PDF}
    store[("talent_pool", "p1")] = {"full_name": "במאגר", "created_at": old}
    store[("maternity_leaves", "m1")] = {"name": "יולדת"}
    store[("annual_budgets", "2025")] = {"year": 2025, "total_budget": 100}
    store[("annual_budgets", "2025", "events", "e1")] = {"name": "חג"}
    store[("annual_budgets", "2025", "events", "e1", "expenses", "x1")] = {"item_name": "פריט", "total_price": 5}
    store[("annual_budgets", "2025", "events", "e1", "expenses", "x1", "invoice_chunks", "0000")] = {"data": PDF}
    store[("settings", "maternity")] = {"notify_recipients": ["hr@x.com"]}
    store[("users", "me@x.com")] = {"role": "admin", "uid": "uid-me@x.com"}  # matches the stub token
    store[("users", "team@x.com")] = {"role": "editor", "uid": "uid-team"}
    store[("jobs", "jb")] = {"job_title": "של B", "owner_id": B}  # already owned: untouched

    def run(apply, cleanup=False):
        writer = m.Writer(w.db._db, apply)
        with contextlib.redirect_stdout(io.StringIO()):
            if cleanup:
                m.cleanup_legacy(w.db, me, writer)
            else:
                m.migrate(w.db, me, "me@x.com", True, "HireTrack", writer)
        writer.flush()
        return writer.writes

    snapshot = dict(store)
    assert run(apply=False) > 0 and store == snapshot  # dry run writes nothing

    run(apply=True)
    assert run(apply=True) == 0  # idempotent
    assert store[("jobs", "jb")]["owner_id"] == B
    assert store[("users", "me@x.com")]["is_super_admin"] is True
    assert store[("users", "team@x.com")]["tenant_id"] == me
    assert "is_super_admin" not in store[("users", "team@x.com")]

    # Everything is visible to the owner's workspace through the app
    c = w.client("me@x.com")
    assert [j["id"] for j in c.get("/api/jobs").json()] == ["j1"]
    assert c.get("/api/jobs/j1/candidates/c1/cv").content == PDF
    assert len(c.get("/api/talent-pool").json()) == 1 and len(c.get("/api/maternity").json()) == 1
    assert c.get("/api/maternity/settings").json()["notify_recipients"] == ["hr@x.com"]
    event = c.get("/api/budgets/2025").json()["events"][0]
    assert event["name"] == "חג"
    assert c.get(f"/api/budgets/2025/events/{event['id']}/expenses").json()[0]["item_name"] == "פריט"
    # ... and nothing of it to another workspace, or to the team member's demo
    assert w.client("admin@b.com").get("/api/budgets").json() == []

    # Legacy copies are kept until cleanup, which removes only what was copied
    assert ("annual_budgets", "2025") in store and ("settings", "maternity") in store
    run(apply=True, cleanup=True)
    assert not any(p[:2] == ("annual_budgets", "2025") for p in store)
    assert ("settings", "maternity") not in store
    assert c.get("/api/budgets/2025").status_code == 200


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
