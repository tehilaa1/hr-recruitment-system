"""Bootstrap (or recover) an admin user.

Creates the Firebase Auth account if needed and writes the `users/{email}`
document with role "admin". Requires server access (the service-account key),
which is why it's a script rather than an API endpoint.

Usage (from the backend/ directory, with the venv active):
    python scripts/create_admin.py admin@company.com --name "שם מלא"

You'll be prompted for a password (min. 6 characters) if the account is new.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dependencies import get_firestore_service  # noqa: E402
from app.models.user import UserCreate  # noqa: E402
from app.services import auth_service  # noqa: E402
from firebase_admin import auth  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin user")
    parser.add_argument("email")
    parser.add_argument("--name", default="", help="Display name")
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
    db.set_user(
        email,
        {
            "display_name": args.name or record.get("display_name", ""),
            "role": "admin",
            "uid": uid,
            "created_at": record.get("created_at") or datetime.now(timezone.utc),
            "created_by": record.get("created_by") or "create_admin script",
        },
    )
    print(f"✓ {email} is now an admin. Log in at the app's /login page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
