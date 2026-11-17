from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Union

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services.budget_service import summarize_expenses
from app.services.invoice_service import split_chunks

logger = logging.getLogger(__name__)


class FirestoreService:
    def __init__(self, credentials_source: Union[dict, str]) -> None:
        """`credentials_source` is a service-account dict or a path to its JSON file."""
        if not firebase_admin._apps:
            try:
                cred = credentials.Certificate(credentials_source)
            except (IOError, ValueError) as exc:
                where = "FIREBASE_CREDENTIALS_JSON" if isinstance(credentials_source, dict) else credentials_source
                logger.error(
                    "Firebase credentials could not be loaded from %s: %s. Set "
                    "FIREBASE_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS.",
                    where, exc,
                )
                raise
            firebase_admin.initialize_app(cred)
        self._db = firestore.client()

    # ------------------------------------------------------------------ #
    # Jobs                                                                 #
    # ------------------------------------------------------------------ #

    def create_job(self, data: dict) -> dict:
        data["created_at"] = datetime.now(timezone.utc)
        ref = self._db.collection("jobs").document()
        ref.set(data)
        return {"id": ref.id, **data}

    def get_job(self, job_id: str) -> Optional[dict]:
        doc = self._db.collection("jobs").document(job_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def list_jobs(self) -> list[dict]:
        docs = (
            self._db.collection("jobs")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def update_job(self, job_id: str, data: dict) -> Optional[dict]:
        ref = self._db.collection("jobs").document(job_id)
        if not ref.get().exists:
            return None
        ref.update(data)
        updated = ref.get()
        return {"id": updated.id, **updated.to_dict()}

    def delete_job(self, job_id: str) -> bool:
        ref = self._db.collection("jobs").document(job_id)
        if not ref.get().exists:
            return False
        for cand in ref.collection("candidates").stream():
            cand.reference.delete()
        ref.delete()
        return True

    def get_candidate_count(self, job_id: str) -> int:
        docs = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .stream()
        )
        return sum(1 for _ in docs)

    # ------------------------------------------------------------------ #
    # Candidates                                                           #
    # ------------------------------------------------------------------ #

    def create_candidate(self, job_id: str, data: dict) -> dict:
        data["job_id"] = job_id
        data["created_at"] = datetime.now(timezone.utc)
        ref = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .document()
        )
        ref.set(data)
        return {"id": ref.id, **data}

    def get_candidate(self, job_id: str, candidate_id: str) -> Optional[dict]:
        doc = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .document(candidate_id)
            .get()
        )
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def list_candidates(self, job_id: str) -> list[dict]:
        docs = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def list_all_candidates(self) -> list[dict]:
        """Every candidate across all jobs (collection-group query, no index needed)."""
        docs = self._db.collection_group("candidates").stream()
        results = []
        for d in docs:
            data = d.to_dict() or {}
            # Path is jobs/{job_id}/candidates/{id}; trust the path over the field
            parent_job = d.reference.parent.parent
            if parent_job is not None:
                data["job_id"] = parent_job.id
            results.append({"id": d.id, **data})
        return results

    def update_candidate(
        self, job_id: str, candidate_id: str, data: dict
    ) -> Optional[dict]:
        ref = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .document(candidate_id)
        )
        if not ref.get().exists:
            return None
        ref.update(data)
        updated = ref.get()
        return {"id": updated.id, **updated.to_dict()}

    # ------------------------------------------------------------------ #
    # Talent pool (top-level; CVs not tied to a job)                       #
    # Its own collection name, so the "candidates" collection-group query  #
    # used by global search never picks these up.                          #
    # ------------------------------------------------------------------ #

    _TALENT_POOL = "talent_pool"

    def create_pool_candidate(self, data: dict) -> dict:
        data["created_at"] = datetime.now(timezone.utc)
        ref = self._db.collection(self._TALENT_POOL).document()
        ref.set(data)
        return {"id": ref.id, **data}

    def get_pool_candidate(self, candidate_id: str) -> Optional[dict]:
        doc = self._db.collection(self._TALENT_POOL).document(candidate_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def list_pool_candidates(self) -> list[dict]:
        docs = (
            self._db.collection(self._TALENT_POOL)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def delete_pool_candidate(self, candidate_id: str) -> bool:
        ref = self._db.collection(self._TALENT_POOL).document(candidate_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # ------------------------------------------------------------------ #
    # Annual budgets: annual_budgets/{year} + events subcollection         #
    # ------------------------------------------------------------------ #

    _BUDGETS = "annual_budgets"

    def _budget_ref(self, year: int):
        return self._db.collection(self._BUDGETS).document(str(year))

    def list_budget_years(self) -> list[dict]:
        return [
            {**d.to_dict(), "year": int(d.id)}
            for d in self._db.collection(self._BUDGETS).stream()
            if d.id.isdigit()
        ]

    def get_budget_year(self, year: int) -> Optional[dict]:
        doc = self._budget_ref(year).get()
        return {**doc.to_dict(), "year": year} if doc.exists else None

    def create_budget_year(self, year: int, data: dict) -> Optional[dict]:
        """None if the year already exists (create() fails atomically, no overwrite)."""
        from google.api_core.exceptions import AlreadyExists

        now = datetime.now(timezone.utc)
        data = {**data, "created_at": now, "updated_at": now}
        data.pop("year", None)
        try:
            self._budget_ref(year).create(data)
        except AlreadyExists:
            return None
        return {**data, "year": year}

    def update_budget_year(self, year: int, data: dict) -> Optional[dict]:
        ref = self._budget_ref(year)
        if not ref.get().exists:
            return None
        ref.update({**data, "updated_at": datetime.now(timezone.utc)})
        return {**ref.get().to_dict(), "year": year}

    def delete_budget_year(self, year: int) -> bool:
        ref = self._budget_ref(year)
        if not ref.get().exists:
            return False
        for event in ref.collection("events").stream():
            self._delete_expenses(event.reference)
            event.reference.delete()
        ref.delete()
        return True

    def _event_ref(self, year: int, event_id: str):
        return self._budget_ref(year).collection("events").document(event_id)

    def get_budget_event(self, year: int, event_id: str) -> Optional[dict]:
        doc = self._event_ref(year, event_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def list_budget_events(self, year: int) -> list[dict]:
        return [{"id": d.id, **d.to_dict()} for d in self._budget_ref(year).collection("events").stream()]

    def create_budget_event(self, year: int, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        data = {**data, "created_at": now, "updated_at": now}
        ref = self._budget_ref(year).collection("events").document()
        ref.set(data)
        return {"id": ref.id, **data}

    def update_budget_event(self, year: int, event_id: str, data: dict) -> Optional[dict]:
        ref = self._event_ref(year, event_id)
        if not ref.get().exists:
            return None
        ref.update({**data, "updated_at": datetime.now(timezone.utc)})
        return {"id": event_id, **ref.get().to_dict()}

    def delete_budget_event(self, year: int, event_id: str) -> bool:
        ref = self._event_ref(year, event_id)
        if not ref.get().exists:
            return False
        self._delete_expenses(ref)
        ref.delete()
        return True

    # Itemized expenses: annual_budgets/{year}/events/{event_id}/expenses/{id}.
    # Every write re-derives the event's actual_spent and expenses_count.

    def list_event_expenses(self, year: int, event_id: str) -> list[dict]:
        docs = self._event_ref(year, event_id).collection("expenses").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def create_event_expense(self, year: int, event_id: str, data: dict) -> Optional[dict]:
        """None if the event doesn't exist."""
        event_ref = self._event_ref(year, event_id)
        if not event_ref.get().exists:
            return None
        now = datetime.now(timezone.utc)
        data = {**data, "created_at": now, "updated_at": now}
        ref = event_ref.collection("expenses").document()
        ref.set(data)
        self._sync_event_spent(event_ref)
        return {"id": ref.id, **data}

    def update_event_expense(
        self, year: int, event_id: str, expense_id: str, data: dict
    ) -> Optional[dict]:
        event_ref = self._event_ref(year, event_id)
        ref = event_ref.collection("expenses").document(expense_id)
        if not ref.get().exists:
            return None
        ref.update({**data, "updated_at": datetime.now(timezone.utc)})
        self._sync_event_spent(event_ref)
        return {"id": expense_id, **ref.get().to_dict()}

    def delete_event_expense(self, year: int, event_id: str, expense_id: str) -> bool:
        event_ref = self._event_ref(year, event_id)
        ref = event_ref.collection("expenses").document(expense_id)
        if not ref.get().exists:
            return False
        self._delete_invoice_chunks(ref)
        ref.delete()
        self._sync_event_spent(event_ref)
        return True

    # Uploaded invoice file of an expense: metadata in the expense's invoice_file
    # field, raw bytes in .../invoice_chunks/{0000, 0001, ...}

    def _expense_ref(self, year: int, event_id: str, expense_id: str):
        return self._event_ref(year, event_id).collection("expenses").document(expense_id)

    def set_expense_invoice(
        self, year: int, event_id: str, expense_id: str, meta: dict, data: bytes
    ) -> Optional[dict]:
        """Store (or replace) the invoice in one atomic batch. None if the expense doesn't exist."""
        ref = self._expense_ref(year, event_id, expense_id)
        if not ref.get().exists:
            return None
        chunks = split_chunks(data)
        chunks_col = ref.collection("invoice_chunks")
        batch = self._db.batch()
        # Same ids are overwritten by set(); only leftovers of a longer old file are deleted
        for old in chunks_col.list_documents():  # references only, no file bytes
            if not old.id.isdigit() or int(old.id) >= len(chunks):
                batch.delete(old)
        for i, part in enumerate(chunks):
            batch.set(chunks_col.document(f"{i:04d}"), {"index": i, "data": part})
        now = datetime.now(timezone.utc)
        batch.update(ref, {"invoice_file": {**meta, "uploaded_at": now}, "updated_at": now})
        batch.commit()
        return {"id": expense_id, **ref.get().to_dict()}

    def get_expense_invoice(
        self, year: int, event_id: str, expense_id: str
    ) -> Optional[tuple[dict, bytes]]:
        """(metadata, bytes), or None if the expense or its file doesn't exist."""
        ref = self._expense_ref(year, event_id, expense_id)
        doc = ref.get()
        meta = (doc.to_dict() or {}).get("invoice_file") if doc.exists else None
        if not isinstance(meta, dict):
            return None
        parts = sorted(
            (d.to_dict() or {} for d in ref.collection("invoice_chunks").stream()),
            key=lambda c: int(c.get("index") or 0),
        )
        data = b"".join(bytes(c.get("data") or b"") for c in parts)
        if len(data) != meta.get("size"):
            logger.error("Invoice of expense %s is incomplete (%s of %s bytes)", expense_id, len(data), meta.get("size"))
            return None
        return meta, data

    def delete_expense_invoice(self, year: int, event_id: str, expense_id: str) -> Optional[dict]:
        ref = self._expense_ref(year, event_id, expense_id)
        if not ref.get().exists:
            return None
        self._delete_invoice_chunks(ref)
        ref.update({"invoice_file": None, "updated_at": datetime.now(timezone.utc)})
        return {"id": expense_id, **ref.get().to_dict()}

    @staticmethod
    def _delete_invoice_chunks(expense_ref) -> None:
        for chunk in expense_ref.collection("invoice_chunks").list_documents():
            chunk.delete()

    def _sync_event_spent(self, event_ref) -> None:
        expenses = [d.to_dict() or {} for d in event_ref.collection("expenses").stream()]
        summary = summarize_expenses(expenses)
        event_ref.update({
            "actual_spent": summary["total"],
            "expenses_count": summary["count"],
            "updated_at": datetime.now(timezone.utc),
        })

    @staticmethod
    def _delete_expenses(event_ref) -> None:
        for expense in event_ref.collection("expenses").stream():
            FirestoreService._delete_invoice_chunks(expense.reference)
            expense.reference.delete()

    # ------------------------------------------------------------------ #
    # Maternity leaves                                                     #
    # ------------------------------------------------------------------ #

    _MATERNITY = "maternity_leaves"

    def create_maternity_leave(self, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        data["created_at"] = now
        data["updated_at"] = now
        ref = self._db.collection(self._MATERNITY).document()
        ref.set(data)
        return {"id": ref.id, **data}

    def list_maternity_leaves(self) -> list[dict]:
        docs = (
            self._db.collection(self._MATERNITY)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def update_maternity_leave(self, record_id: str, data: dict) -> Optional[dict]:
        ref = self._db.collection(self._MATERNITY).document(record_id)
        if not ref.get().exists:
            return None
        ref.update({**data, "updated_at": datetime.now(timezone.utc)})
        updated = ref.get()
        return {"id": updated.id, **updated.to_dict()}

    def delete_maternity_leave(self, record_id: str) -> bool:
        ref = self._db.collection(self._MATERNITY).document(record_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # ------------------------------------------------------------------ #
    # Users (document id = lower-cased email)                              #
    # ------------------------------------------------------------------ #

    def get_user(self, email: str) -> Optional[dict]:
        doc = self._db.collection("users").document(email).get()
        return {"email": doc.id, **doc.to_dict()} if doc.exists else None

    def list_users(self) -> list[dict]:
        return [{"email": d.id, **d.to_dict()} for d in self._db.collection("users").stream()]

    def set_user(self, email: str, data: dict) -> dict:
        self._db.collection("users").document(email).set(data)
        return {"email": email, **data}

    def update_user(self, email: str, data: dict) -> Optional[dict]:
        ref = self._db.collection("users").document(email)
        if not ref.get().exists:
            return None
        ref.update(data)
        return {"email": email, **ref.get().to_dict()}

    def delete_user(self, email: str) -> bool:
        ref = self._db.collection("users").document(email)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # Password reset state (OTP / token hashes); document id = lower-cased email
    def get_password_reset(self, email: str) -> Optional[dict]:
        doc = self._db.collection("password_resets").document(email).get()
        return doc.to_dict() if doc.exists else None

    def set_password_reset(self, email: str, data: dict) -> None:
        self._db.collection("password_resets").document(email).set(data)

    def delete_password_reset(self, email: str) -> None:
        self._db.collection("password_resets").document(email).delete()

    def count_admins(self) -> int:
        docs = (
            self._db.collection("users")
            .where(filter=FieldFilter("role", "==", "admin"))
            .stream()
        )
        return sum(1 for _ in docs)

    # ------------------------------------------------------------------ #
    # Settings documents                                                   #
    # ------------------------------------------------------------------ #

    def get_settings_doc(self, name: str) -> dict:
        doc = self._db.collection("settings").document(name).get()
        if not doc.exists:
            return {}
        return doc.to_dict() or {}

    def set_settings_doc(self, name: str, data: dict) -> dict:
        self._db.collection("settings").document(name).set(data)
        return data

    def delete_candidate(self, job_id: str, candidate_id: str) -> bool:
        ref = (
            self._db.collection("jobs")
            .document(job_id)
            .collection("candidates")
            .document(candidate_id)
        )
        if not ref.get().exists:
            return False
        ref.delete()
        return True
