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
    TEMPLATE_PLACEHOLDERS,
    BabyGender,
    MaternityLeaveBase,
    MaternityLeaveCreate,
    MaternityLeaveResponse,
    MaternityLeaveUpdate,
    MaternitySettings,
    MaternityTemplates,
)

FRONTEND_COLUMNS = (
    BACKEND_DIR.parent / "frontend" / "src" / "constants" / "maternityColumns.js"
)
FRONTEND_TEMPLATES = (
    BACKEND_DIR.parent / "frontend" / "src" / "utils" / "maternityTemplates.js"
)


def _templates_object(name: str) -> str:
    source = FRONTEND_TEMPLATES.read_text(encoding="utf-8")
    match = re.search(rf"export const {name}\s*=\s*\{{(.*?)\n\}};", source, re.S)
    assert match, f"{name} not found in {FRONTEND_TEMPLATES}"
    return match.group(1)


def _top_level_keys(body: str) -> list[str]:
    # Object keys at two-space indentation, e.g. "  name: 'שם העובדת',"
    return re.findall(r"^  (\w+):", body, re.M)


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


def test_template_placeholders_match_frontend():
    assert _top_level_keys(_templates_object("TEMPLATE_PLACEHOLDERS")) == list(TEMPLATE_PLACEHOLDERS)


def test_template_keys_match_frontend_defaults():
    assert set(_top_level_keys(_templates_object("DEFAULT_TEMPLATES"))) == set(
        MaternityTemplates.model_fields
    )


def test_default_templates_use_only_known_placeholders():
    used = set(re.findall(r"\{(\w+)\}", _templates_object("DEFAULT_TEMPLATES")))
    assert used, "no placeholders found in DEFAULT_TEMPLATES"
    assert used <= set(TEMPLATE_PLACEHOLDERS), used - set(TEMPLATE_PLACEHOLDERS)


def test_templates_validation():
    t = MaternityTemplates(initial_body="מזל טוב ל{name}! {baby_phrase}", full_body="   ")
    assert t.initial_body.startswith("מזל טוב") and t.full_body == ""
    for bad in ("{nmae}", "{}", "x" * 5001):
        try:
            MaternityTemplates(full_body=bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid template {bad[:20]!r}")
    # Plain braces that aren't placeholders (e.g. with spaces) are just text
    assert MaternityTemplates(full_body="{ not a field }").full_body == "{ not a field }"


def test_settings_without_templates_load_with_defaults():
    s = MaternitySettings.model_validate({"notify_recipients": ["a@b.com"]})
    assert s.templates == MaternityTemplates()
    assert "templates" not in MaternitySettings(notify_recipients=[]).model_fields_set


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
