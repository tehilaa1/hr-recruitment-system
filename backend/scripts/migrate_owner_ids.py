"""Assign all existing (pre multi-tenant) data to your workspace.

Your workspace's tenant id is your Firebase Auth uid. The script:

  1. creates tenants/{uid} if missing
  2. sets owner_id = uid on every job, job candidate (all jobs), talent-pool
     entry and maternity record that has NO owner_id yet
     (records that already have one are never touched)
  3. copies legacy budgets annual_budgets/{year} (with all events, expenses
     and invoice files) to annual_budgets/{uid}__{year}
  4. copies legacy settings/{name} to settings/{uid}__{name}
  5. sets tenant_id = uid on every user document that has none (your team), and
     marks --email as super admin when --super-admin is given

DRY RUN by default: only prints what it would do. Add --apply to write.
Safe to run again: everything already migrated is skipped.
Legacy budget/settings documents are kept until you run --cleanup-legacy
(after checking the app), which deletes only those whose copy exists.

Usage (from backend/, venv active):
    python scripts/migrate_owner_ids.py --email you@company.com --super-admin
    python scripts/migrate_owner_ids.py --email you@company.com --super-admin --apply
    python scripts/migrate_owner_ids.py --email you@company.com --cleanup-legacy --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.dependencies import get_firestore_service  # noqa: E402
from app.models.user import normalize_user_email  # noqa: E402
from app.services.firestore_service import (  # noqa: E402
    OWNER_FIELD,
    FirestoreService,
    check_owner_id,
)
from firebase_admin import auth  # noqa: E402

TOP_LEVEL = ("jobs", "talent_pool", "maternity_leaves")
BATCH_LIMIT = 400


class Writer:
    """Batches writes; in dry-run mode only counts them."""

    def __init__(self, db, apply: bool) -> None:
        self._db = db
        self.apply = apply
        self._batch = db.batch() if apply else None
        self._pending = 0
        self.writes = 0

    def _op(self, fn, *args) -> None:
        self.writes += 1
        if not self.apply:
            return
        fn(*args)
        self._pending += 1
        if self._pending >= BATCH_LIMIT:
            self.flush()

    def set(self, ref, data) -> None:
        self._op(lambda r, d: self._batch.set(r, d), ref, data)

    def update(self, ref, data) -> None:
        self._op(lambda r, d: self._batch.update(r, d), ref, data)

    def delete(self, ref) -> None:
        self._op(lambda r: self._batch.delete(r), ref)

    def flush(self) -> None:
        if self.apply and self._pending:
            self._batch.commit()
            self._batch = self._db.batch()
            self._pending = 0


def _is_legacy_budget_id(doc_id: str) -> bool:
    return doc_id.isdigit()


def _is_legacy_settings_id(doc_id: str) -> bool:
    return "__" not in doc_id


def copy_tree(src_ref, dst_ref, w: Writer, root_extra: dict | None = None) -> int:
    """Copy a document and all its subcollections recursively. Returns documents copied."""
    snap = src_ref.get()
    if not snap.exists:
        return 0
    w.set(dst_ref, {**(snap.to_dict() or {}), **(root_extra or {})})
    copied = 1
    for sub in src_ref.collections():
        for child in sub.stream():
            copied += copy_tree(child.reference, dst_ref.collection(sub.id).document(child.id), w)
    return copied


def delete_tree(ref, w: Writer) -> int:
    deleted = 0
    for sub in ref.collections():
        for child in sub.list_documents():
            deleted += delete_tree(child, w)
    w.delete(ref)
    return deleted + 1


def migrate(db, tenant: str, email: str, super_admin: bool, workspace_name: str, w: Writer) -> None:
    raw = db._db
    now = datetime.now(timezone.utc)

    # 1. Workspace document
    if db.get_tenant(tenant) is None:
        print(f"• create tenants/{tenant} ({workspace_name!r})")
        w.set(raw.collection("tenants").document(tenant),
              {"name": workspace_name, "created_at": now, "created_by": "migrate_owner_ids"})

    # 2. Owner on records that have none
    for name in TOP_LEVEL:
        n = 0
        for doc in raw.collection(name).stream():
            if OWNER_FIELD not in (doc.to_dict() or {}):
                w.update(doc.reference, {OWNER_FIELD: tenant})
                n += 1
        print(f"• {name}: {n} record(s) without owner → {tenant}")

    n = 0
    for doc in raw.collection_group("candidates").stream():
        if OWNER_FIELD in (doc.to_dict() or {}):
            continue
        job = doc.reference.parent.parent
        job_owner = (job.get().to_dict() or {}).get(OWNER_FIELD) if job is not None else None
        if job_owner not in (None, tenant):
            # Belongs to a job of another workspace: never guess, report it
            print(f"  ! skipped candidate {doc.reference.path}: its job belongs to {job_owner}")
            continue
        w.update(doc.reference, {OWNER_FIELD: tenant})
        n += 1
    print(f"• job candidates: {n} record(s) without owner → {tenant}")

    # 3. Budgets annual_budgets/{year} → {tenant}__{year}
    for doc in raw.collection("annual_budgets").stream():
        if not _is_legacy_budget_id(doc.id):
            continue
        dst = raw.collection("annual_budgets").document(FirestoreService.budget_doc_id(tenant, int(doc.id)))
        if dst.get().exists:
            print(f"• budget {doc.id}: already copied to {dst.id} (skipped)")
            continue
        copied = copy_tree(doc.reference, dst, w, {OWNER_FIELD: tenant, "year": int(doc.id)})
        print(f"• budget {doc.id} → {dst.id} ({copied} document(s) incl. events/expenses/invoices)")

    # 4. Settings settings/{name} → {tenant}__{name}
    for doc in raw.collection("settings").stream():
        if not _is_legacy_settings_id(doc.id):
            continue
        dst = raw.collection("settings").document(FirestoreService.settings_doc_id(tenant, doc.id))
        if dst.get().exists:
            print(f"• settings/{doc.id}: already copied (skipped)")
            continue
        w.set(dst, {**(doc.to_dict() or {}), OWNER_FIELD: tenant})
        print(f"• settings/{doc.id} → settings/{dst.id}")

    # 5. Users
    n = 0
    for doc in raw.collection("users").stream():
        data = doc.to_dict() or {}
        update = {}
        if not data.get("tenant_id"):
            update["tenant_id"] = tenant
        if super_admin and doc.id == email and data.get("is_super_admin") is not True:
            update["is_super_admin"] = True
        if update:
            w.update(doc.reference, update)
            n += 1
            print(f"  user {doc.id}: {update}")
    print(f"• users: {n} updated")


def cleanup_legacy(db, tenant: str, w: Writer) -> None:
    raw = db._db
    for doc in raw.collection("annual_budgets").stream():
        if not _is_legacy_budget_id(doc.id):
            continue
        dst = raw.collection("annual_budgets").document(FirestoreService.budget_doc_id(tenant, int(doc.id)))
        if not dst.get().exists:
            print(f"! budget {doc.id}: no migrated copy — kept")
            continue
        print(f"• delete legacy budget {doc.id} ({delete_tree(doc.reference, w)} document(s))")
    for doc in raw.collection("settings").stream():
        if not _is_legacy_settings_id(doc.id):
            continue
        if not raw.collection("settings").document(FirestoreService.settings_doc_id(tenant, doc.id)).get().exists:
            print(f"! settings/{doc.id}: no migrated copy — kept")
            continue
        print(f"• delete legacy settings/{doc.id}")
        w.delete(doc.reference)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assign pre multi-tenant data to your workspace")
    parser.add_argument("--email", required=True, help="Your (the data owner's) login email")
    parser.add_argument("--super-admin", action="store_true", help="Mark --email as super admin")
    parser.add_argument("--workspace-name", default="HireTrack")
    parser.add_argument("--cleanup-legacy", action="store_true",
                        help="Delete legacy budget/settings docs that were already copied")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    email = normalize_user_email(args.email)
    db = get_firestore_service()  # initializes firebase_admin
    try:
        tenant = check_owner_id(auth.get_user_by_email(email).uid)
    except auth.UserNotFoundError:
        print(f"No Firebase Auth account for {email}")
        return 1
    if tenant == get_settings().DEMO_TENANT_ID:
        print("Refusing: that is the demo workspace id")
        return 1
    record = db.get_user(email)
    if record is None or record.get("uid") != tenant:
        print(f"{email} has no users/ document linked to uid {tenant}; run create_admin.py first")
        return 1

    mode = "APPLY" if args.apply else "DRY RUN (nothing is written; add --apply)"
    print(f"{mode} — workspace {tenant} ({email})\n")
    w = Writer(db._db, args.apply)
    if args.cleanup_legacy:
        cleanup_legacy(db, tenant, w)
    else:
        migrate(db, tenant, email, args.super_admin, args.workspace_name, w)
    w.flush()
    print(f"\n{w.writes} write(s) {'done' if args.apply else 'planned'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
