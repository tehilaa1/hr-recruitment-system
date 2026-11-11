"""Guards that recruitment statuses stay in sync between backend and frontend.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_status_sync.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.candidate import (  # noqa: E402
    DEFAULT_STATUS,
    CandidateStatusUpdate,
    RecruitmentStatus,
    VALID_STATUSES,
)

FRONTEND_STATUSES = BACKEND_DIR.parent / "frontend" / "src" / "constants" / "statuses.js"


def _frontend_block(name: str) -> str:
    source = FRONTEND_STATUSES.read_text(encoding="utf-8")
    match = re.search(rf"export const {name}\s*=\s*([\[{{].*?[\]}}]);", source, re.S)
    assert match, f"{name} not found in {FRONTEND_STATUSES}"
    return match.group(1)


def _frontend_statuses() -> list[str]:
    return re.findall(r"'([^']+)'", _frontend_block("RECRUITMENT_STATUSES"))


def _frontend_styled_statuses() -> set[str]:
    # Top-level keys of STATUS_STYLES look like:  'גויס/ה': {
    return set(re.findall(r"'([^']+)'\s*:\s*\{", _frontend_block("STATUS_STYLES")))


def test_literal_matches_tuple():
    assert get_args(RecruitmentStatus) == VALID_STATUSES


def test_frontend_list_matches_backend():
    assert _frontend_statuses() == list(VALID_STATUSES)


def test_every_status_has_frontend_style():
    missing = set(VALID_STATUSES) - _frontend_styled_statuses()
    assert not missing, f"STATUS_STYLES is missing: {missing}"


def test_default_status_is_valid():
    assert DEFAULT_STATUS == "לא טופל"


def test_hired_status_is_accepted_and_unknown_rejected():
    assert CandidateStatusUpdate(recruitment_status="גויס/ה").recruitment_status == "גויס/ה"
    try:
        CandidateStatusUpdate(recruitment_status="hired")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown status was accepted")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
