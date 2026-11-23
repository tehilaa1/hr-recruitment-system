"""Free-tier protection for the public demo workspace.

Applies only when ``user.is_demo``; real workspaces are never limited here.

The daily AI counter is kept in process memory: it resets when the server
restarts (Render's free tier sleeps after inactivity), which is acceptable for
a demo. Every other limit is stateless.
"""
from __future__ import annotations

import threading
from datetime import date
from typing import Iterable

from fastapi import HTTPException, UploadFile
from fastapi import status as http_status

from app.config import get_settings

DEMO_AI_LIMIT_MESSAGE = "הגעתם למכסת הניתוחים היומית של חשבון ההדגמה. נסו שוב מחר."


class _DailyCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day = date.today()
        self._used = 0

    def consume(self, amount: int, limit: int) -> bool:
        """Reserve `amount` units for today; False (nothing reserved) if it would exceed `limit`."""
        with self._lock:
            today = date.today()
            if today != self._day:
                self._day, self._used = today, 0
            if self._used + amount > limit:
                return False
            self._used += amount
            return True

    def reset(self) -> None:
        with self._lock:
            self._day, self._used = date.today(), 0


demo_ai_counter = _DailyCounter()


def consume_demo_ai(user, calls: int = 1) -> None:
    """429 if the demo workspace has used up today's Gemini calls."""
    if not user.is_demo or calls <= 0:
        return
    if not demo_ai_counter.consume(calls, get_settings().DEMO_AI_DAILY_LIMIT):
        raise HTTPException(http_status.HTTP_429_TOO_MANY_REQUESTS, DEMO_AI_LIMIT_MESSAGE)


def max_upload_bytes(user, default: int) -> int:
    return min(default, get_settings().DEMO_MAX_UPLOAD_BYTES) if user.is_demo else default


def check_demo_uploads(user, files: Iterable[UploadFile]) -> None:
    """Limit file count and size of a demo batch upload before anything is parsed."""
    if not user.is_demo:
        return
    settings = get_settings()
    files = list(files)
    if len(files) > settings.DEMO_MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"בחשבון ההדגמה ניתן להעלות עד {settings.DEMO_MAX_FILES_PER_UPLOAD} קבצים בכל פעם",
        )
    limit = settings.DEMO_MAX_UPLOAD_BYTES
    for upload in files:
        size = upload.size
        if size is None:  # not reported by the client: measure it
            upload.file.seek(0, 2)
            size = upload.file.tell()
            upload.file.seek(0)
        if size > limit:
            raise HTTPException(
                http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"בחשבון ההדגמה גודל קובץ מוגבל ל-{limit // (1024 * 1024)}MB",
            )


def check_demo_record_cap(user, current_count: int, adding: int = 1) -> None:
    if not user.is_demo:
        return
    cap = get_settings().DEMO_MAX_RECORDS
    if current_count + adding > cap:
        raise HTTPException(
            http_status.HTTP_403_FORBIDDEN,
            f"חשבון ההדגמה מוגבל ל-{cap} רשומות בכל מודול",
        )
