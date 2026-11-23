"""In-memory stand-in for the Firestore client, covering only what FirestoreService
uses in the tests (documents, subcollections, batches, order_by, where, collection_group).

    db = FirestoreService.__new__(FirestoreService)   # skips Firebase initialization
    db._db = FakeFirestore()
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class _Snap:
    def __init__(self, ref, data):
        self.reference, self.id, self._data = ref, ref.id, data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class _Doc:
    def __init__(self, store, path):
        self._store, self.path, self.id = store, path, path[-1]

    @property
    def parent(self):
        return _Col(self._store, self.path[:-1])

    def get(self):
        return _Snap(self, self._store.get(self.path))

    def create(self, data):
        from google.api_core.exceptions import AlreadyExists

        if self.path in self._store:
            raise AlreadyExists("exists")
        self.set(data)

    def set(self, data):
        self._store[self.path] = copy.deepcopy(data)

    def update(self, data):
        if self.path not in self._store:
            raise KeyError(self.path)
        self._store[self.path].update(copy.deepcopy(data))

    def delete(self):
        self._store.pop(self.path, None)

    def collection(self, name):
        return _Col(self._store, self.path + (name,))

    def collections(self):
        n = len(self.path) + 1
        names = sorted({p[n - 1] for p in self._store if len(p) > n and p[: n - 1] == self.path})
        return [_Col(self._store, self.path + (name,)) for name in names]


class _Filtered:
    """A query with where(filter=FieldFilter(...)) clauses (only "==" is used)."""

    def __init__(self, source, filters):
        self._source, self._filters = source, filters

    def where(self, filter=None):
        assert filter.op_string == "==", filter.op_string
        return _Filtered(self._source, self._filters + [filter])

    def stream(self):
        return [
            s for s in self._source()
            if all((s.to_dict() or {}).get(f.field_path) == f.value for f in self._filters)
        ]


class _Col:
    _next = 0

    def __init__(self, store, path):
        self._store, self.path, self.id = store, path, path[-1]

    @property
    def parent(self):
        return _Doc(self._store, self.path[:-1]) if len(self.path) > 1 else None

    def document(self, doc_id=None):
        if doc_id is None:
            _Col._next += 1
            doc_id = f"auto{_Col._next:05d}"
        return _Doc(self._store, self.path + (doc_id,))

    def list_documents(self):
        n = len(self.path) + 1
        return [_Doc(self._store, p) for p in sorted(self._store) if len(p) == n and p[:-1] == self.path]

    def stream(self):
        return [d.get() for d in self.list_documents()]

    def where(self, filter=None):
        return _Filtered(self.stream, []).where(filter=filter)

    def order_by(self, field, direction=None):
        return _Ordered(self.stream, field, descending=str(direction).upper().endswith("DESCENDING"))


class _Ordered:
    def __init__(self, source, field, descending):
        self._source, self._field, self._desc = source, field, descending

    def stream(self):
        # Like Firestore, documents without the field are left out
        snaps = [s for s in self._source() if (s.to_dict() or {}).get(self._field) is not None]
        return sorted(snaps, key=lambda s: s.to_dict()[self._field], reverse=self._desc)


class _Group:
    def __init__(self, store, name):
        self._store, self._name = store, name

    def stream(self):
        return [_Doc(self._store, p).get() for p in sorted(self._store) if len(p) % 2 == 0 and p[-2] == self._name]

    def where(self, filter=None):
        return _Filtered(self.stream, []).where(filter=filter)


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

    def collection_group(self, name):
        return _Group(self.store, name)

    def batch(self):
        return _Batch()

    def chunk_paths(self):
        return sorted(p for p in self.store if "invoice_chunks" in p)


TENANT = "tenant-a"


def member(tenant: str = TENANT, email: str = "user@a.com", role: str = "admin", **flags):
    """A CurrentUser of `tenant`, for app.dependency_overrides[get_current_user]."""
    from app.security import CurrentUser

    return CurrentUser(uid=f"uid-{email}", email=email, role=role, tenant_id=tenant, **flags)


def sign_in(app, user=None):
    """Make every request of `app` come from `user` (default: an admin of TENANT)."""
    from app.security import get_current_user

    user = user or member()
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def fake_service():
    """(FakeFirestore, FirestoreService running on it)."""
    from app.services.firestore_service import FirestoreService

    fake = FakeFirestore()
    db = FirestoreService.__new__(FirestoreService)
    db._db = fake
    return fake, db
