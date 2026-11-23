"""Bootstrap (or recover) an admin user.

Creates the Firebase Auth account if needed and writes the `users/{email}`
document with role "admin". Requires server access (the service-account key),
which is why it's a script rather than an API endpoint.

Every user belongs to exactly one workspace (tenant_id):
  * an existing user keeps their workspace
  * --tenant ID         adds the admin to an existing workspace
  * --new-workspace NAME creates a new, empty, isolated workspace for them
    (its id is the admin's uid, unless --tenant is also given)
  * --super-admin       may also create workspaces / reset the demo in the app

Usage (from the backend/ directory, with the venv active):
    python scripts/create_admin.py admin@company.com --name "שם מלא" --new-workspace "Acme"
    python scripts/create_admin.py second@company.com --tenant <workspace id>

You'll be prompted for a password (min. 6 characters) if the account is new.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.dependencies import get_firestore_service  # noqa: E402
from app.models.user import UserCreate  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.services.firestore_service import check_owner_id  # noqa: E402
from firebase_admin import auth  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin user")
    parser.add_argument("email")
    parser.add_argument("--name", default="", help="Display name")
    parser.add_argument("--tenant", help="Workspace id to join (or to create with --new-workspace)")
    parser.add_argument("--new-workspace", metavar="NAME", help="Create a new workspace with this name")
    parser.add_argument("--super-admin", action="store_true", help="Grant super admin")
    args = parser.parse_args()

    email = UserCreate(email=args.email).email  # validates + normalizes
    db = get_firestore_service()  # also initializes firebase_admin

    try:
        existing_uid = auth.get_user_by_email(email).uid
    except auth.UserNotFoundError:
        existing_uid = None

    if existing_uid:
        print(f"A Firebase Auth account for {email} already exists (uid {existing_uid}).")
        if input("Link it as admin? [y/N] ").strip().lower() != "y":
            return 1
        uid = existing_uid
    else:
        password = getpass.getpass("Password for the new account (min 6 chars): ")
        if len(password) < 6 or password != getpass.getpass("Repeat password: "):
            print("Passwords don't match or are too short.")
            return 1
        uid, _ = auth_service.get_or_create_account(email, args.name, password=password)

    record = db.get_user(email) or {}
    try:
        tenant_id = resolve_tenant(db, args, record, uid)
    except ValueError as exc:
        print(exc)
        return 1

    db.set_user(
        email,
        {
            "display_name": args.name or record.get("display_name", ""),
            "role": "admin",
            "uid": uid,
            "tenant_id": tenant_id,
            "is_super_admin": args.super_admin or record.get("is_super_admin") is True,
            "created_at": record.get("created_at") or datetime.now(timezone.utc),
            "created_by": record.get("created_by") or "create_admin script",
        },
    )
    print(f"✓ {email} is now an admin of workspace {tenant_id}. Log in at the app's /login page.")
    return 0


def resolve_tenant(db, args, record: dict, uid: str) -> str:
    demo = get_settings().DEMO_TENANT_ID
    current = record.get("tenant_id")
    if current == demo:
        raise ValueError("This is the public demo account; it can't be an admin.")
    if args.new_workspace:
        if current:
            raise ValueError(f"This user already belongs to workspace {current}.")
        tenant_id = check_owner_id(args.tenant or uid)
        if tenant_id == demo or db.get_tenant(tenant_id):
            raise ValueError(f"Workspace {tenant_id} already exists.")
        db.set_tenant(tenant_id, {
            "name": args.new_workspace,
            "created_at": datetime.now(timezone.utc),
            "created_by": "create_admin script",
        })
        return tenant_id
    if args.tenant:
        tenant_id = check_owner_id(args.tenant)
        if current and current != tenant_id:
            raise ValueError(f"This user already belongs to workspace {current}.")
        if tenant_id == demo:
            raise ValueError("The demo workspace can't have admins.")
        if db.get_tenant(tenant_id) is None:
            raise ValueError(f"No workspace {tenant_id} (use --new-workspace to create it).")
        return tenant_id
    if current:
        return current
    raise ValueError("New users need --tenant <id> or --new-workspace <name>.")


if __name__ == "__main__":
    sys.exit(main())
