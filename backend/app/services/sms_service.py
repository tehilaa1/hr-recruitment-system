"""Outgoing SMS (verification codes).

Providers (settings.SMS_PROVIDER):
  console – simulation for development: the message is written to the server
            log only. Nothing is sent.
  twilio  – Twilio REST API over plain HTTPS (no extra dependency).
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

from app.models.user import mask_phone

logger = logging.getLogger(__name__)


class SmsError(Exception):
    """The SMS could not be sent."""


class SmsSender(Protocol):
    name: str

    def send(self, to_e164: str, text: str) -> None: ...


class ConsoleSmsSender:
    """Development fallback: logs the message instead of sending it."""

    name = "console"

    def send(self, to_e164: str, text: str) -> None:
        logger.warning("[SMS simulation — not sent] to %s: %s", mask_phone(to_e164), text)


class TwilioSmsSender:
    name = "twilio"
    _URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def __init__(self, account_sid: str, auth_token: str, sender: str, timeout: float = 10) -> None:
        self._sid = account_sid
        self._token = auth_token
        self._sender = sender
        self._timeout = timeout

    def send(self, to_e164: str, text: str) -> None:
        fields = {"To": to_e164, "Body": text}
        # A Messaging Service SID starts with "MG"; otherwise it's a phone number
        fields["MessagingServiceSid" if self._sender.startswith("MG") else "From"] = self._sender
        request = urllib.request.Request(
            self._URL.format(sid=urllib.parse.quote(self._sid)),
            data=urllib.parse.urlencode(fields).encode(),
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{self._sid}:{self._token}".encode()).decode(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                sid = json.loads(resp.read() or b"{}").get("sid")
                logger.info("SMS sent to %s (twilio sid %s)", mask_phone(to_e164), sid)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            logger.error("Twilio rejected SMS to %s: %s %s", mask_phone(to_e164), exc.code, detail)
            raise SmsError("שליחת ה-SMS נכשלה") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.error("Twilio unreachable for SMS to %s: %s", mask_phone(to_e164), exc)
            raise SmsError("שליחת ה-SMS נכשלה") from exc


def build_sms_sender(settings) -> SmsSender:
    if settings.SMS_PROVIDER == "twilio":
        missing = [
            k for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")
            if not getattr(settings, k)
        ]
        if missing:
            raise RuntimeError(f"SMS_PROVIDER=twilio but {', '.join(missing)} not set")
        return TwilioSmsSender(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER
        )
    return ConsoleSmsSender()
