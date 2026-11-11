"""Guards that maternity-leave columns stay in sync between backend and frontend.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_maternity_fields_sync.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.maternity import MaternityLeaveBase, MaternityLeaveUpdate  # noqa: E402

FRONTEND_COLUMNS = (
    BACKEND_DIR.parent / "frontend" / "src" / "constants" / "maternityColumns.js"
)


def _frontend_field_keys() -> set[str]:
    source = FRONTEND_COLUMNS.read_text(encoding="utf-8")
    all_keys = set(re.findall(r"key:\s*'(\w+)'", source))
    # "group" entries are table/form layout only, not data fields
    group_keys = set(re.findall(r"key:\s*'(\w+)',[^{}]*?type:\s*'group'", source))
    return all_keys - group_keys


def test_frontend_columns_match_backend_model():
    backend = set(MaternityLeaveBase.model_fields)
    frontend = _frontend_field_keys()
    assert frontend == backend, (
        f"only in frontend: {frontend - backend or '-'}; only in backend: {backend - frontend or '-'}"
    )


def test_update_model_covers_all_fields():
    assert set(MaternityLeaveUpdate.model_fields) == set(MaternityLeaveBase.model_fields)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
