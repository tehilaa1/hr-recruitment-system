"""Expense invoice files: validation helpers, and the real FirestoreService +
budgets router running on an in-memory Firestore stand-in.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_invoices.py)
"""
from __future__ import annotations

import copy
import io
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from app.dependencies import get_firestore_service  # noqa: E402
from app.models.budget import INVOICE_MAX_BYTES, ExpenseResponse  # noqa: E402
from app.routers import budgets  # noqa: E402
from app.services import firestore_service as fs_module  # noqa: E402
from app.services import invoice_service  # noqa: E402
from app.services.firestore_service import FirestoreService  # noqa: E402
from app.services.invoice_service import (  # noqa: E402
    detect_content_type,
    inline_disposition,
    safe_file_name,
    split_chunks,
)

PDF = b"%PDF-1.7\n" + b"x" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ------------------------------------------------------------------ #
# Minimal in-memory Firestore (only what FirestoreService uses here)   #
# ------------------------------------------------------------------ #


class _Snap:
    def __init__(self, ref, data):
        self.reference, self.id, self._data = ref, ref.id, data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class _Doc:
    def __init__(self, store, path):
        self._store, self.path, self.id = store, path, path[-1]

    def get(self):
        return _Snap(self, self._store.get(self.path))

    def set(self, data):
        self._store[self.path] = copy.deepcopy(data)

    def create(self, data):
        if self.path in self._store:
            raise ValueError("exists")
        self.set(data)

    def update(self, data):
        if self.path not in self._store:
            raise KeyError(self.path)
        self._store[self.path].update(copy.deepcopy(data))

    def delete(self):
        self._store.pop(self.path, None)

    def collection(self, name):
        return _Col(self._store, self.path + (name,))


class _Col:
    _next = 0

    def __init__(self, store, path):
        self._store, self.path = store, path

    def document(self, doc_id=None):
        if doc_id is None:
            _Col._next += 1
            doc_id = f"auto{_Col._next}"
        return _Doc(self._store, self.path + (doc_id,))

    def list_documents(self):
        n = len(self.path) + 1
        return [_Doc(self._store, p) for p in sorted(self._store) if len(p) == n and p[:-1] == self.path]

    def stream(self):
        return [d.get() for d in self.list_documents()]


class _Batch:
    def __init__(self):
        self._ops = []

    def set(self, ref, data):
        self._ops.append(lambda: ref.set(data))

    def update(self, ref, data):
        self._ops.append(lambda: ref.update(data))

    def delete(self, ref):
        self._ops.append(ref.delete)

    def commit(self):
        for op in self._ops:
            op()


class FakeFirestore:
    def __init__(self):
        self.store: dict[tuple, dict] = {}

    def collection(self, name):
        return _Col(self.store, (name,))

    def batch(self):
        return _Batch()

    def chunk_paths(self):
        return sorted(p for p in self.store if "invoice_chunks" in p)


def _setup():
    fake = FakeFirestore()
    db = FirestoreService.__new__(FirestoreService)  # skip Firebase initialization
    db._db = fake
    db.create_budget_year(2026, {"total_budget": 10000})
    event = db.create_budget_event(2026, {"name": "חנוכה", "allocated_budget": 5000})
    app = FastAPI()
    app.include_router(budgets.router)
    app.dependency_overrides[get_firestore_service] = lambda: db
    return fake, db, TestClient(app), f"/api/budgets/2026/events/{event['id']}"


def _upload(client, url, content, name="חשבונית.pdf", mime="application/pdf"):
    return client.put(url, files={"file": (name, io.BytesIO(content), mime)})


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #


def test_detects_real_type_by_content():
    assert detect_content_type(PDF) == "application/pdf"
    assert detect_content_type(PNG) == "image/png"
    assert detect_content_type(JPG) == "image/jpeg"
    assert detect_content_type(b"\xef\xbb\xbf%PDF-1.4") == "application/pdf"
    for bad in (b"", b"<html><script>", b"MZ\x90\x00", b"GIF89a"):
        assert detect_content_type(bad) is None


def test_file_names_are_sanitized():
    assert safe_file_name("../../חשבונית 12.PNG", "image/png") == "חשבונית 12.png"
    assert safe_file_name("C:\\scans\\inv.pdf", "application/pdf") == "inv.pdf"
    assert safe_file_name("evil.exe", "image/jpeg") == "evil.jpg"  # extension follows the content
    assert safe_file_name(None, "application/pdf") == "invoice.pdf"
    assert safe_file_name("a\x00b\nc.pdf", "application/pdf") == "abc.pdf"
    header = inline_disposition("חשבונית.pdf")
    assert header.startswith('inline; filename="invoice.pdf"') and "%D7%97" in header
    assert '"' not in inline_disposition('a"b.pdf').split("filename=")[1][1:-30]


def test_chunks_cover_the_file_exactly():
    data = bytes(range(256)) * 10
    parts = split_chunks(data, 1000)
    assert [len(p) for p in parts] == [1000, 1000, 560] and b"".join(parts) == data
    assert invoice_service.CHUNK_BYTES < 1_000_000  # under Firestore's 1 MiB document limit


def test_response_tolerates_broken_metadata():
    assert ExpenseResponse(id="a", invoice_file="oops").invoice_file is None
    assert ExpenseResponse(id="a", invoice_file={"file_name": "x"}).invoice_file is None
    ok = ExpenseResponse(id="a", invoice_file={"file_name": "x.pdf", "content_type": "application/pdf", "size": 3})
    assert ok.invoice_file.size == 3


def test_upload_view_replace_and_remove():
    fake, db, client, base = _setup()
    expense = client.post(f"{base}/expenses", json={"item_name": "סופגניות", "total_price": 1350}).json()
    url = f"{base}/expenses/{expense['id']}/invoice"

    assert client.get(url).status_code == 404  # nothing attached yet

    # Multi-chunk file: force small chunks so a 2.5 KB file spans 3 documents
    fs_module.split_chunks = lambda data: split_chunks(data, 1000)
    try:
        big = b"%PDF-1.7\n" + bytes(range(256)) * 10
        r = _upload(client, url, big, name="../חשבונית ספק.PDF")
        assert r.status_code == 200, r.text
        meta = r.json()["invoice_file"]
        assert meta["file_name"] == "חשבונית ספק.pdf" and meta["size"] == len(big)
        assert meta["content_type"] == "application/pdf" and meta["uploaded_at"]
        assert len(fake.chunk_paths()) == 3

        got = client.get(url)
        assert got.status_code == 200 and got.content == big
        assert got.headers["content-type"] == "application/pdf"
        assert got.headers["x-content-type-options"] == "nosniff"
        assert got.headers["content-disposition"].startswith("inline;")

        # The list carries metadata only; the bytes stay in the chunk documents
        listed = client.get(f"{base}/expenses").json()[0]
        assert listed["invoice_file"]["size"] == len(big) and "data" not in str(listed)

        # Replacing with a smaller file leaves no stale chunks behind
        r = _upload(client, url, PNG, name="scan.png", mime="image/png")
        assert r.json()["invoice_file"]["content_type"] == "image/png"
        assert len(fake.chunk_paths()) == 1
        assert client.get(url).content == PNG
    finally:
        fs_module.split_chunks = split_chunks

    # Other expense fields are untouched by uploads; editing keeps the file
    r = client.patch(f"{base}/expenses/{expense['id']}", json={"status": "שולם"})
    assert r.json()["invoice_file"]["file_name"] == "scan.png"
    assert db.get_budget_event(2026, base.rsplit("/", 1)[1])["actual_spent"] == 1350

    r = client.delete(url)
    assert r.status_code == 200 and r.json()["invoice_file"] is None
    assert fake.chunk_paths() == [] and client.get(url).status_code == 404


def test_upload_rejects_bad_files():
    _, _, client, base = _setup()
    expense = client.post(f"{base}/expenses", json={"item_name": "x"}).json()
    url = f"{base}/expenses/{expense['id']}/invoice"
    # A renamed HTML/exe file is refused even with a PDF name and MIME type
    assert _upload(client, url, b"<html><script>alert(1)</script>").status_code == 415
    assert _upload(client, url, b"").status_code == 422
    too_big = b"%PDF-" + b"0" * INVOICE_MAX_BYTES
    assert _upload(client, url, too_big).status_code == 413
    assert _upload(client, f"{base}/expenses/nope/invoice", PDF).status_code == 404
    assert client.get(f"{base}/expenses").json()[0]["invoice_file"] is None


def test_deleting_expense_event_or_year_removes_files():
    fake, db, client, base = _setup()
    ids = [client.post(f"{base}/expenses", json={"item_name": n}).json()["id"] for n in ("a", "b")]
    for i in ids:
        assert _upload(client, f"{base}/expenses/{i}/invoice", JPG, "r.jpg", "image/jpeg").status_code == 200
    assert len(fake.chunk_paths()) == 2

    assert client.delete(f"{base}/expenses/{ids[0]}").status_code == 204
    assert len(fake.chunk_paths()) == 1

    assert client.delete(base).status_code == 204  # the event
    assert fake.chunk_paths() == []
    assert not any("expenses" in p for p in fake.store)


def test_expenses_excel_lists_attached_file_name():
    _, _, client, base = _setup()
    expense = client.post(f"{base}/expenses", json={"item_name": "סופגניות", "total_price": 100}).json()
    _upload(client, f"{base}/expenses/{expense['id']}/invoice", PDF, "חשבונית 7.pdf")
    ws = load_workbook(io.BytesIO(client.get(f"{base}/export-excel").content)).active
    headers = [c.value for c in ws[3]]
    assert ws.cell(4, headers.index("קובץ חשבונית") + 1).value == "חשבונית 7.pdf"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
