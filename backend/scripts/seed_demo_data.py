"""Create the public demo account and fill its isolated workspace with sample data.

  * Firebase Auth account DEMO_EMAIL with password DEMO_PASSWORD (both from the
    env / env. file); the password is (re)set on every run so it matches the
    frontend's VITE_DEMO_PASSWORD
  * users/{DEMO_EMAIL}: role "editor", tenant_id = DEMO_TENANT_ID — so it can't
    manage users, and the password-reset flow refuses it
  * tenants/{DEMO_TENANT_ID}
  * sample jobs, candidates with PDF CVs, talent pool, budgets and maternity
    records — written only with owner_id = DEMO_TENANT_ID

Idempotent: without --reset, an already seeded workspace is left as is.
--reset deletes every record whose owner_id is the demo workspace (and nothing
else) and seeds again. The same reset is available to super admins at
POST /api/admin/demo/reset.

Usage (from backend/, venv active):
    python scripts/seed_demo_data.py            # first time / no-op if seeded
    python scripts/seed_demo_data.py --reset    # wipe + re-seed the demo only
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
from app.services import auth_service  # noqa: E402
from app.services.demo_seed import reset_demo, seed_demo  # noqa: E402
from app.services.firestore_service import check_owner_id  # noqa: E402
from app.services.password_policy import password_problems  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and seed the demo workspace")
    parser.add_argument("--reset", action="store_true", help="Wipe the demo workspace and seed again")
    args = parser.parse_args()

    settings = get_settings()
    email = normalize_user_email(settings.DEMO_EMAIL)
    tenant = check_owner_id(settings.DEMO_TENANT_ID)
    password = settings.DEMO_PASSWORD
    if not password:
        print("Set DEMO_PASSWORD in the env. file (the same value as the frontend's VITE_DEMO_PASSWORD).")
        return 1
    problems = password_problems(password, email)
    if problems:
        print("DEMO_PASSWORD is too weak: " + " · ".join(problems))
        return 1

    db = get_firestore_service()  # initializes firebase_admin

    record = db.get_user(email)
    if record is not None and record.get("tenant_id") not in (None, tenant):
        print(f"Refusing: {email} belongs to workspace {record['tenant_id']!r}, not the demo.")
        return 1
    if record is not None and (record.get("role") == "admin" or record.get("is_super_admin")):
        print(f"Refusing: {email} is an admin; the public demo account must be a plain editor.")
        return 1

    uid, created = auth_service.get_or_create_account(email, "חשבון הדגמה", password=password)
    if not created:
        auth_service.set_password(uid, password)
    print(f"✓ Demo login {email} ({'created' if created else 'password synced'})")

    now = datetime.now(timezone.utc)
    if db.get_tenant(tenant) is None:
        db.set_tenant(tenant, {"name": "סביבת הדגמה", "created_at": now, "created_by": "seed_demo_data"})
    db.set_user(email, {
        "display_name": "חשבון הדגמה",
        "role": "editor",
        "phone": "",  # no phone: the SMS password reset can never target it
        "uid": uid,
        "tenant_id": tenant,
        "created_at": (record or {}).get("created_at") or now,
        "created_by": "seed_demo_data",
    })

    if args.reset:
        result = reset_demo(db, tenant, settings.DEMO_TENANT_ID)
        print(f"✓ Demo workspace reset. Deleted: {result['deleted']}")
        print(f"  Created: {result['created']}")
    else:
        created_counts = seed_demo(db, tenant)
        if created_counts:
            print(f"✓ Demo workspace seeded: {created_counts}")
        else:
            print("✓ Demo workspace already has data (use --reset to start over)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
