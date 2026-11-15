"""Password reset with SMS code: policy, matching, OTP lifecycle and abuse limits.

No Firebase or SMS access — the store, SMS sender and clock are fakes.
Run:  cd backend && python -m pytest tests/      (or: python tests/test_password_reset.py)
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models.user import (  # noqa: E402
    PasswordResetConfirm,
    UserCreate,
    UserUpdate,
    mask_phone,
    normalize_phone_e164,
)
from app.services import password_reset_service as prs  # noqa: E402
from app.services.password_policy import (  # noqa: E402
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    password_problems,
)
from app.services.sms_service import SmsError  # noqa: E402

FRONTEND_POLICY = BACKEND_DIR.parent / "frontend" / "src" / "utils" / "passwordPolicy.js"
EMAIL = "dana@company.com"
STRONG = "Sunny-Garden-2026"


# ------------------------------------------------------------------ #
# Fakes                                                                #
# ------------------------------------------------------------------ #


class Store:
    def __init__(self, users=None):
        self.users = users or {}
        self.resets: dict = {}

    def get_user(self, email):
        return self.users.get(email)

    def get_password_reset(self, email):
        r = self.resets.get(email)
        return dict(r) if r else None

    def set_password_reset(self, email, data):
        self.resets[email] = dict(data)

    def delete_password_reset(self, email):
        self.resets.pop(email, None)


class Sms:
    name = "fake"

    def __init__(self, fail=False):
        self.sent: list = []
        self.fail = fail

    def send(self, to, text):
        if self.fail:
            raise SmsError("down")
        self.sent.append((to, text))

    def last_code(self):
        return re.search(r"\b(\d{6})\b", self.sent[-1][1]).group(1)


class Clock:
    def __init__(self):
        self.t = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def _setup(user=None, dev_mode=False, sms=None):
    user = user if user is not None else {"uid": "u1", "phone": "+972501234567", "role": "editor"}
    store, sms, clock = Store({EMAIL: user} if user else {}), sms or Sms(), Clock()
    changed, revoked = [], []
    svc = prs.PasswordResetService(
        store, sms,
        set_password=lambda uid, pw: changed.append((uid, pw)),
        revoke_sessions=revoked.append,
        dev_mode=dev_mode, now=clock,
    )
    return svc, store, sms, clock, changed, revoked


def _raises(fn, *args, contains=""):
    try:
        fn(*args)
    except (prs.ResetError, ValueError) as exc:
        assert contains in str(getattr(exc, "message", exc)), exc
        return exc
    raise AssertionError("expected an error")


# ------------------------------------------------------------------ #
# Happy path                                                           #
# ------------------------------------------------------------------ #


def test_full_flow_changes_password_and_revokes_sessions():
    svc, store, sms, clock, changed, revoked = _setup()
    outcome = svc.request(EMAIL)
    assert outcome.sent and outcome.dev_code is None
    assert sms.sent[0][0] == "+972501234567"
    code = sms.last_code()
    assert code not in str(store.resets)  # only a hash is stored

    token = svc.verify(EMAIL, code)
    assert token not in str(store.resets)
    svc.confirm(EMAIL, token, STRONG)
    assert changed == [("u1", STRONG)] and revoked == ["u1"]
    assert EMAIL not in store.resets


def test_dev_mode_returns_code():
    svc, *_ = _setup(dev_mode=True)
    outcome = svc.request(EMAIL)
    assert outcome.dev_code and len(outcome.dev_code) == 6


# ------------------------------------------------------------------ #
# No account enumeration                                               #
# ------------------------------------------------------------------ #


def test_unknown_or_phoneless_accounts_send_nothing_silently():
    for user in ({}, {"uid": "u1", "phone": ""}, {"phone": "+972501234567"}):
        svc, store, sms, *_ = _setup(user=user)
        outcome = svc.request(EMAIL)
        assert not outcome.sent and not sms.sent and not store.resets
    svc, *_ = _setup(user={})
    _raises(svc.verify, EMAIL, "123456", contains="שגוי")


# ------------------------------------------------------------------ #
# Abuse limits                                                         #
# ------------------------------------------------------------------ #


def test_wrong_codes_burn_the_code_after_max_attempts():
    svc, store, sms, *_ = _setup()
    svc.request(EMAIL)
    good = sms.last_code()
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(prs.MAX_ATTEMPTS):
        _raises(svc.verify, EMAIL, wrong)
    _raises(svc.verify, EMAIL, good)  # even the right code is now rejected


def test_code_expires():
    svc, store, sms, clock, *_ = _setup()
    svc.request(EMAIL)
    clock.advance(minutes=11)
    _raises(svc.verify, EMAIL, sms.last_code())


def test_code_is_single_use():
    svc, store, sms, *_ = _setup()
    svc.request(EMAIL)
    code = sms.last_code()
    svc.verify(EMAIL, code)
    _raises(svc.verify, EMAIL, code)


def test_resend_cooldown_and_hourly_limit():
    svc, store, sms, clock, *_ = _setup()
    assert svc.request(EMAIL).sent
    assert not svc.request(EMAIL).sent  # within cooldown
    for _ in range(prs.MAX_SENDS_PER_HOUR - 1):
        clock.advance(seconds=61)
        assert svc.request(EMAIL).sent
    clock.advance(seconds=61)
    assert not svc.request(EMAIL).sent  # hourly limit
    clock.advance(hours=1)
    assert svc.request(EMAIL).sent
    # only the newest code works
    assert svc.verify(EMAIL, sms.last_code())


def test_token_expires_and_cannot_be_forged_or_replayed():
    svc, store, sms, clock, changed, _ = _setup()
    svc.request(EMAIL)
    token = svc.verify(EMAIL, sms.last_code())
    _raises(svc.confirm, EMAIL, "x" * 43, STRONG, contains="פג")
    clock.advance(minutes=11)
    _raises(svc.confirm, EMAIL, token, STRONG, contains="פג")
    assert not changed

    svc, store, sms, clock, changed, _ = _setup()
    svc.request(EMAIL)
    token = svc.verify(EMAIL, sms.last_code())
    svc.confirm(EMAIL, token, STRONG)
    _raises(svc.confirm, EMAIL, token, STRONG)
    assert len(changed) == 1


def test_sms_failure_is_reported_and_nothing_stored():
    svc, store, *_ = _setup(sms=Sms(fail=True))
    exc = _raises(svc.request, EMAIL, contains="SMS")
    assert exc.status_code == 502 and not store.resets


# ------------------------------------------------------------------ #
# Password policy & confirmation                                       #
# ------------------------------------------------------------------ #


def test_password_policy():
    assert password_problems(STRONG, EMAIL) == []
    assert password_problems("סיסמה-חזקה-77", EMAIL) == []  # Hebrew letters count
    for weak in ("short1", "onlyletters-here", "1234567890", "aaaa111111", "password123", "dana-2026-xyz"):
        assert password_problems(weak, EMAIL), weak


def test_confirm_requires_matching_strong_passwords():
    ok = dict(email=EMAIL, reset_token="t" * 43)
    assert PasswordResetConfirm(**ok, new_password=STRONG, confirm_password=STRONG)
    exc = _raises(lambda: PasswordResetConfirm(**ok, new_password=STRONG, confirm_password=STRONG + "x"))
    assert "אינן תואמות" in str(exc)
    exc = _raises(lambda: PasswordResetConfirm(**ok, new_password="abc", confirm_password="abc"))
    assert f"לפחות {PASSWORD_MIN_LENGTH}" in str(exc)


def test_frontend_policy_constants_match_backend():
    source = FRONTEND_POLICY.read_text(encoding="utf-8")
    assert re.search(rf"PASSWORD_MIN_LENGTH\s*=\s*{PASSWORD_MIN_LENGTH}\b", source)
    assert re.search(rf"PASSWORD_MAX_LENGTH\s*=\s*{PASSWORD_MAX_LENGTH}\b", source)


# ------------------------------------------------------------------ #
# User phone                                                           #
# ------------------------------------------------------------------ #


def test_user_phone_normalized_to_e164():
    assert normalize_phone_e164("050-123-4567") == "+972501234567"
    assert normalize_phone_e164("+1 (415) 555-0100") == "+14155550100"
    assert UserCreate(email="A@B.com", phone=" 052 7654321 ").phone == "+972527654321"
    assert UserUpdate(phone="").phone == "" and UserUpdate().phone is None
    _raises(lambda: UserCreate(email="a@b.com", phone="123"))
    assert mask_phone("+972501234567").endswith("4567") and "5012" not in mask_phone("+972501234567")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
