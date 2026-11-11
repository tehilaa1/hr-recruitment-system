from __future__ import annotations

import re
from typing import Any, Optional

_MIN_PHONE_DIGITS = 7


def normalize_email(value: Any) -> str:
    return str(value).strip().lower() if value else ""


def normalize_phone(value: Any) -> str:
    """Reduce a phone number to comparable digits.

    "+972-50-123-4567", "972501234567" and "050 1234567" all become "0501234567".
    Returns "" for values too short to be a real number, so blanks never match.
    """
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("00972"):
        digits = "0" + digits[5:]
    elif digits.startswith("972"):
        digits = "0" + digits[3:]
    return digits if len(digits) >= _MIN_PHONE_DIGITS else ""


class CandidateDeduplicator:
    """Tracks the emails/phones already present for a job.

    Built once per upload request from the existing candidates, then updated
    as new candidates are inserted so duplicates within the same batch are
    caught too.
    """

    def __init__(self, existing: list[dict]) -> None:
        self._by_email: dict[str, dict] = {}
        self._by_phone: dict[str, dict] = {}
        for candidate in existing:
            self.add(candidate)

    def add(self, candidate: dict) -> None:
        email = normalize_email(candidate.get("email"))
        phone = normalize_phone(candidate.get("phone"))
        if email:
            self._by_email.setdefault(email, candidate)
        if phone:
            self._by_phone.setdefault(phone, candidate)

    def find(self, candidate: dict) -> Optional[tuple[str, dict]]:
        """Return ("email" | "phone", existing_candidate) on a match, else None."""
        email = normalize_email(candidate.get("email"))
        if email and email in self._by_email:
            return "email", self._by_email[email]
        phone = normalize_phone(candidate.get("phone"))
        if phone and phone in self._by_phone:
            return "phone", self._by_phone[phone]
        return None
