"""Password strength rules (Hebrew messages).

The frontend shows the same rules as a live checklist in
frontend/src/utils/passwordPolicy.js; PASSWORD_MIN_LENGTH / PASSWORD_MAX_LENGTH
must match there (enforced by tests/test_password_reset.py).
"""
from __future__ import annotations

import re

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# Very common passwords / patterns that pass the character rules
_COMMON = {
    "password1", "password12", "password123", "password1234", "passw0rd123",
    "qwerty1234", "qwerty12345", "1q2w3e4r5t", "abc1234567", "abcd123456",
    "a123456789", "1234567890a", "iloveyou123", "welcome123", "admin12345",
    "letmein123", "shalom1234", "israel1234",
}


def password_problems(password: str, email: str = "") -> list[str]:
    """Every rule the password breaks, as Hebrew sentences ([] = strong enough)."""
    pw = password or ""
    problems: list[str] = []
    if len(pw) < PASSWORD_MIN_LENGTH:
        problems.append(f"הסיסמה חייבת להכיל לפחות {PASSWORD_MIN_LENGTH} תווים")
    if len(pw) > PASSWORD_MAX_LENGTH:
        problems.append(f"הסיסמה יכולה להכיל עד {PASSWORD_MAX_LENGTH} תווים")
    if not re.search(r"[A-Za-z֐-׿]", pw):
        problems.append("הסיסמה חייבת להכיל לפחות אות אחת")
    if not re.search(r"\d", pw):
        problems.append("הסיסמה חייבת להכיל לפחות ספרה אחת")
    if pw != pw.strip():
        problems.append("הסיסמה לא יכולה להתחיל או להסתיים ברווח")
    if pw and len(set(pw)) < 4:
        problems.append("הסיסמה פשוטה מדי (מעט מדי תווים שונים)")
    if pw.lower() in _COMMON:
        problems.append("הסיסמה נפוצה מדי – בחרו סיסמה אחרת")
    local = (email or "").split("@", 1)[0].lower()
    if len(local) >= 3 and local in pw.lower():
        problems.append("הסיסמה לא יכולה להכיל את שם המשתמש")
    return problems


def passwords_match_problems(new_password: str, confirm_password: str) -> list[str]:
    return [] if new_password == confirm_password else ["הסיסמאות אינן תואמות"]
