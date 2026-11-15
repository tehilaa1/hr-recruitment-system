"""Guards for frontend pieces that must agree with the backend or with each other.

Run:  cd backend && python -m pytest tests/      (or: python tests/test_frontend_contracts.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.candidate import CandidateCreate, CandidateManualBase  # noqa: E402

FRONTEND_SRC = BACKEND_DIR.parent / "frontend" / "src"


def _read(rel: str) -> str:
    return (FRONTEND_SRC / rel).read_text(encoding="utf-8")


def test_every_module_has_a_route():
    """A module in constants/modules.js shows on Home + Navbar, so it needs a route."""
    modules = re.findall(r"path:\s*'([^']+)'", _read("constants/modules.js"))
    routes = set(re.findall(r'<Route\s+path="([^"]+)"', _read("App.jsx")))
    assert modules, "no modules found"
    assert "/talent-pool" in modules
    missing = [m for m in modules if m not in routes]
    assert not missing, f"modules without a <Route>: {missing}"


def test_manual_candidate_form_matches_backend_model():
    """CandidateFormModal's fields == the manual-entry model (+ status for jobs)."""
    source = _read("components/CandidateFormModal.jsx")
    block = re.search(r"const EMPTY\s*=\s*\{(.*?)\};", source, re.S)
    assert block, "EMPTY not found in CandidateFormModal.jsx"
    form_keys = set(re.findall(r"^\s*(\w+):", block.group(1), re.M))
    assert form_keys - {"recruitment_status"} == set(CandidateManualBase.model_fields)
    assert form_keys == set(CandidateCreate.model_fields)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
