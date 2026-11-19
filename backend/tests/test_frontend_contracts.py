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
from app.services.cv_file_service import CV_UPLOAD_EXTENSIONS  # noqa: E402

FRONTEND_SRC = BACKEND_DIR.parent / "frontend" / "src"


def _read(rel: str) -> str:
    return (FRONTEND_SRC / rel).read_text(encoding="utf-8")


def test_every_module_has_a_route():
    """A module in constants/modules.js shows on Home + Navbar, so it needs a route."""
    modules = re.findall(r"path:\s*'([^']+)'", _read("constants/modules.js"))
    routes = set(re.findall(r'<Route\s+path="([^"]+)"', _read("App.jsx")))
    assert modules, "no modules found"
    missing = [m for m in modules if m not in routes]
    assert not missing, f"modules without a <Route>: {missing}"


def test_talent_pool_and_all_candidates_are_one_module():
    """The talent pool and "all candidates" are a single module at /candidates;
    the old /talent-pool URL redirects there instead of breaking."""
    modules = re.findall(r"path:\s*'([^']+)'", _read("constants/modules.js"))
    assert "/candidates" in modules
    assert "/talent-pool" not in modules
    app = _read("App.jsx")
    assert re.search(r'<Route\s+path="/talent-pool/\*"\s+element=\{<Navigate to="/candidates" replace />\}', app)
    for gone in ("pages/TalentPool.jsx", "pages/AllCandidates.jsx"):
        assert not (FRONTEND_SRC / gone).exists(), f"{gone} should be merged into pages/Candidates.jsx"
    # No in-app link still points at the old route
    for path in FRONTEND_SRC.rglob("*.js*"):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"['\"`]/talent-pool", text):
            assert path.name == "App.jsx", f"{path.relative_to(FRONTEND_SRC)} links to /talent-pool"


def test_cv_accept_list_matches_backend():
    source = _read("utils/candidateCv.js")
    accept = re.search(r"CV_ACCEPT\s*=\s*'([^']+)'", source).group(1)
    assert {e.lstrip(".") for e in accept.split(",")} == CV_UPLOAD_EXTENSIONS


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
