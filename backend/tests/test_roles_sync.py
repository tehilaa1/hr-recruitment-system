"""Guards that user roles stay in sync between backend and frontend.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_roles_sync.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.user import VALID_ROLES, Role  # noqa: E402

FRONTEND_ROLES = BACKEND_DIR.parent / "frontend" / "src" / "constants" / "roles.js"


def _frontend_roles() -> list[str]:
    source = FRONTEND_ROLES.read_text(encoding="utf-8")
    block = re.search(r"export const ROLES\s*=\s*\[(.*?)\];", source, re.S)
    assert block, "ROLES not found in roles.js"
    return re.findall(r"value:\s*'(\w+)'", block.group(1))


def test_literal_matches_tuple():
    assert get_args(Role) == VALID_ROLES


def test_frontend_roles_match_backend():
    assert _frontend_roles() == list(VALID_ROLES)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
