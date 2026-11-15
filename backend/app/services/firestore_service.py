from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Union

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

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
