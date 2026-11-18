"""In-memory stand-in for the Firestore client, covering only what FirestoreService
uses in the tests (documents, subcollections, batches, order_by, collection_group).

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
        if self.path in self._store:
            raise ValueError("exists")
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


class _Col:
    _next = 0

    def __init__(self, store, path):
        self._store, self.path = store, path

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


def fake_service():
    """(FakeFirestore, FirestoreService running on it)."""
    from app.services.firestore_service import FirestoreService

    fake = FakeFirestore()
    db = FirestoreService.__new__(FirestoreService)
    db._db = fake
    return fake, db
