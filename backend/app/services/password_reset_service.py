"""Password reset with SMS verification (OTP).

Flow:
  1. request(email)  – a 6-digit code is texted to the phone saved on the user
                       (by an admin, in User Management).
  2. verify(email, code) – a correct code is exchanged for a single-use
                       reset token (the code itself is then consumed).
  3. confirm(email, token, new_password) – the Firebase password is changed
                       and all existing sessions are signed out.

Security notes
  * Codes and tokens are stored only as salted SHA-256 hashes, in the
    `password_resets` collection (document id = email), and expire quickly.
  * A code allows MAX_ATTEMPTS wrong guesses, then it is discarded.
  * Sending is limited (RESEND_COOLDOWN, MAX_SENDS_PER_HOUR) per account.
  * request() answers the same way whether or not the account exists or has a
    phone, so the endpoint can't be used to discover accounts.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Protocol

from app.models.user import mask_phone
from app.services.sms_service import SmsError, SmsSender

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
TOKEN_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_SENDS_PER_HOUR = 5

GENERIC_REQUEST_MESSAGE = (
    "אם קיים חשבון עם כתובת זו ומוגדר לו מספר טלפון, נשלח אליו קוד אימות ב-SMS."
)
_BAD_CODE = "הקוד שגוי או שפג תוקפו. ניתן לבקש קוד חדש."
_BAD_TOKEN = "תוקף האימות פג. התחילו את תהליך איפוס הסיסמה מחדש."


class ResetError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ResetStore(Protocol):
    def get_user(self, email: str) -> Optional[dict]: ...
    def get_password_reset(self, email: str) -> Optional[dict]: ...
    def set_password_reset(self, email: str, data: dict) -> None: ...
    def delete_password_reset(self, email: str) -> None: ...


@dataclass
class RequestOutcome:
    sent: bool
    dev_code: Optional[str] = None


def _hash(salt: str, secret: str) -> str:
    return hashlib.sha256(f"{salt}:{secret}".encode()).hexdigest()


def _aware(value) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class PasswordResetService:
    def __init__(
        self,
        store: ResetStore,
        sms: SmsSender,
        set_password: Callable[[str, str], None],
        revoke_sessions: Callable[[str], None] = lambda uid: None,
        dev_mode: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store = store
        self._sms = sms
        self._set_password = set_password
        self._revoke = revoke_sessions
        self._dev_mode = dev_mode
        self._now = now

    # ------------------------------------------------------------------ #
    # 1. Send a code                                                       #
    # ------------------------------------------------------------------ #

    def request(self, email: str) -> RequestOutcome:
        user = self._store.get_user(email)
        phone = (user or {}).get("phone") or ""
        if not user or not user.get("uid") or not phone:
            logger.info("Password reset requested for %s: no account or no phone — nothing sent", email)
            return RequestOutcome(sent=False)

        now = self._now()
        record = self._store.get_password_reset(email) or {}
        recent = [
            t for t in (_aware(x) for x in record.get("send_times") or [])
            if t and now - t < timedelta(hours=1)
        ]
        if recent and now - max(recent) < RESEND_COOLDOWN:
            logger.info("Password reset for %s: resend cooldown — nothing sent", email)
            return RequestOutcome(sent=False)
        if len(recent) >= MAX_SENDS_PER_HOUR:
            logger.warning("Password reset for %s: hourly SMS limit reached — nothing sent", email)
            return RequestOutcome(sent=False)

        code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
        salt = secrets.token_hex(16)
        minutes = int(CODE_TTL.total_seconds() // 60)
        text = (
            f"HireTrack: קוד האימות לאיפוס הסיסמה הוא {code}. "
            f"הקוד בתוקף {minutes} דקות. אם לא ביקשת לאפס סיסמה, התעלם/י מהודעה זו."
        )
        try:
            self._sms.send(phone, text)
        except SmsError as exc:
            raise ResetError("שליחת ה-SMS נכשלה. נסו שוב בעוד כמה דקות.", 502) from exc

        self._store.set_password_reset(
            email,
            {
                "code_hash": _hash(salt, code),
                "salt": salt,
                "code_expires_at": now + CODE_TTL,
                "attempts": 0,
                "send_times": recent + [now],
                "token_hash": None,
                "token_expires_at": None,
            },
        )
        logger.info("Password reset code sent to %s (%s) via %s", email, mask_phone(phone), self._sms.name)
        return RequestOutcome(sent=True, dev_code=code if self._dev_mode else None)

    # ------------------------------------------------------------------ #
    # 2. Check the code → single-use reset token                          #
    # ------------------------------------------------------------------ #

    def verify(self, email: str, code: str) -> str:
        record = self._store.get_password_reset(email)
        now = self._now()
        expires = _aware((record or {}).get("code_expires_at"))
        if (
            not record
            or not record.get("code_hash")
            or not expires
            or now >= expires
            or int(record.get("attempts") or 0) >= MAX_ATTEMPTS
        ):
            raise ResetError(_BAD_CODE)

        if not hmac.compare_digest(_hash(record["salt"], code), record["code_hash"]):
            attempts = int(record.get("attempts") or 0) + 1
            update = {**record, "attempts": attempts}
            if attempts >= MAX_ATTEMPTS:
                logger.warning("Password reset for %s: too many wrong codes — code discarded", email)
                update.update(code_hash=None, code_expires_at=None)
            self._store.set_password_reset(email, update)
            raise ResetError(_BAD_CODE)

        token = secrets.token_urlsafe(32)
        self._store.set_password_reset(
            email,
            {
                **record,
                # The code is consumed; only the token can be used from now on
                "code_hash": None,
                "code_expires_at": None,
                "token_hash": _hash(record["salt"], token),
                "token_expires_at": now + TOKEN_TTL,
            },
        )
        return token

    # ------------------------------------------------------------------ #
    # 3. Change the password                                               #
    # ------------------------------------------------------------------ #

    def confirm(self, email: str, token: str, new_password: str) -> None:
        record = self._store.get_password_reset(email)
        expires = _aware((record or {}).get("token_expires_at"))
        if (
            not record
            or not record.get("token_hash")
            or not expires
            or self._now() >= expires
            or not hmac.compare_digest(_hash(record["salt"], token), record["token_hash"])
        ):
            raise ResetError(_BAD_TOKEN)

        user = self._store.get_user(email)
        if not user or not user.get("uid"):
            self._store.delete_password_reset(email)
            raise ResetError(_BAD_TOKEN)

        try:
            self._set_password(user["uid"], new_password)
        except ValueError as exc:  # Firebase rejected the password
            raise ResetError(f"הסיסמה נדחתה: {exc}") from exc
        # Single use: the token can't be replayed
        self._store.delete_password_reset(email)
        # Sign out every existing session of this account
        self._revoke(user["uid"])
        logger.info("Password reset completed for %s", email)
