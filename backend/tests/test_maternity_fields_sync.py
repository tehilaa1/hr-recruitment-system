"""Guards that maternity-leave columns stay in sync between backend and frontend.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_maternity_fields_sync.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.maternity import (  # noqa: E402
    BABY_GENDERS,
    BabyGender,
    MaternityLeaveBase,
    MaternityLeaveCreate,
    MaternityLeaveResponse,
    MaternityLeaveUpdate,
)

FRONTEND_COLUMNS = (
    BACKEND_DIR.parent / "frontend" / "src" / "constants" / "maternityColumns.js"
)


def _source() -> str:
    return FRONTEND_COLUMNS.read_text(encoding="utf-8")


def _block(name: str) -> str:
    match = re.search(rf"export const {name}\s*=\s*\[(.*?)\n\];", _source(), re.S)
    assert match, f"{name} not found in {FRONTEND_COLUMNS}"
    return match.group(1)


def _keys(block: str) -> set[str]:
    all_keys = set(re.findall(r"key:\s*'(\w+)'", block))
    # "group" entries are table/form layout only, not data fields
    group_keys = set(re.findall(r"key:\s*'(\w+)',[^{}]*?type:\s*'group'", block))
    return all_keys - group_keys


def _column_keys() -> set[str]:
    return _keys(_block("MATERNITY_COLUMNS"))


def _status_keys() -> set[str]:
    return _keys(_block("MATERNITY_STATUS_FIELDS"))


def test_frontend_columns_match_backend_model():
    backend = set(MaternityLeaveBase.model_fields)
    frontend = _column_keys() | _status_keys()
    assert frontend == backend, (
        f"only in frontend: {frontend - backend or '-'}; only in backend: {backend - frontend or '-'}"
    )


def test_status_fields_are_booleans_outside_the_form():
    status = _status_keys()
    assert status == {"is_completed"}
    assert not status & _column_keys(), "status flags must not also be form/table columns"
    for key in status:
        assert MaternityLeaveBase.model_fields[key].annotation is bool, key
        assert MaternityLeaveBase.model_fields[key].default is False, key


def test_is_completed_defaults_false_and_is_partially_updatable():
    assert MaternityLeaveCreate(name="דנה").is_completed is False
    assert MaternityLeaveUpdate(is_completed=True).model_dump(exclude_unset=True) == {
        "is_completed": True
    }


def test_update_model_covers_all_fields():
    assert set(MaternityLeaveUpdate.model_fields) == set(MaternityLeaveBase.model_fields)


def _frontend_options(key: str) -> list[str]:
    entry = re.search(rf"\{{\s*key:\s*'{key}'[^{{}}]*?options:\s*\[([^\]]*)\]", _source())
    assert entry, f"no options for {key!r} in {FRONTEND_COLUMNS}"
    return re.findall(r"'([^']+)'", entry.group(1))


def test_baby_gender_options_match_backend():
    assert get_args(BabyGender) == BABY_GENDERS
    assert _frontend_options("baby_gender") == list(BABY_GENDERS)


def test_baby_gender_validation():
    assert MaternityLeaveCreate(name="דנה", baby_gender="בת").baby_gender == "בת"
    # The form sends "" when nothing is chosen; it is stored as null
    assert MaternityLeaveCreate(name="דנה", baby_gender="").baby_gender is None
    assert MaternityLeaveUpdate(baby_gender="").model_dump(exclude_unset=True) == {"baby_gender": None}
    try:
        MaternityLeaveCreate(name="דנה", baby_gender="boy")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown baby_gender was accepted")
    # Reading never fails on an unexpected stored value
    assert MaternityLeaveResponse(id="r1", baby_gender="boy").baby_gender is None
    assert MaternityLeaveResponse(id="r1").baby_gender is None


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
