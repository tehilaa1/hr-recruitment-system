"""Shared CV upload pipeline used by job uploads and the talent pool.

1. Validate extensions and read every file.
2. Parse all CVs with Gemini *concurrently* (bounded by the service's semaphore).
3. Deduplicate in upload order, so duplicates inside the same batch are caught
   deterministically (the first file wins).
4. Save the new candidates to Firestore concurrently.

One failing file never fails the batch — each file gets its own result.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from fastapi import UploadFile

from app.services.dedup_service import CandidateDeduplicator
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "docx", "doc"}


async def ingest_cvs(
    files: list[UploadFile],
    ai: GeminiService,
    dedup: CandidateDeduplicator,
    save: Callable[[dict], dict],
    duplicate_message: Callable[[str, dict], str],
    extra_fields: dict | None = None,
) -> list[dict]:
    """Returns one dict per file, in upload order, with the keys
    file_name, success, candidate (saved record or None), error, duplicate, duplicate_of_id.

    `save` is a blocking Firestore write (run in a thread) that returns the saved record.
    """
    results: list[dict] = []
    to_parse: list[tuple[int, bytes, str, str]] = []

    for upload in files:
        file_name = upload.filename or "unknown"
        result = _result(file_name)
        results.append(result)

        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext not in ALLOWED_EXTENSIONS:
            result["error"] = (
                f"סוג קובץ לא נתמך '.{ext}'. "
                f"מותר: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
            continue
        try:
            content = await upload.read()
        except Exception as exc:
            logger.exception("Failed to read uploaded file %r", file_name)
            result["error"] = f"קריאת הקובץ נכשלה: {exc}"
            continue
        content_type = upload.content_type or "application/octet-stream"
        to_parse.append((len(results) - 1, content, file_name, content_type))

    # --- 2. parse in parallel ---------------------------------------- #
    parsed_list = await asyncio.gather(
        *(ai.parse_cv_async(content, name, ctype) for _, content, name, ctype in to_parse),
        return_exceptions=True,
    )

    # --- 3. dedup in upload order ------------------------------------ #
    pending_saves: list[tuple[int, dict]] = []
    duplicates: list[tuple[int, str, dict]] = []
    for (idx, _, file_name, _), parsed in zip(to_parse, parsed_list):
        if isinstance(parsed, BaseException):
            logger.error("Failed to parse %r: %s", file_name, parsed)
            results[idx]["error"] = str(parsed) or "עיבוד הקובץ נכשל"
            continue

        match = dedup.find(parsed)
        if match:
            field, existing = match
            logger.info(
                "Skipping duplicate candidate from %r (matched on %s, existing id %s)",
                file_name, field, existing.get("id"),
            )
            duplicates.append((idx, field, existing))
            continue

        record = {**parsed, **(extra_fields or {}), "file_name": file_name}
        # Registered before saving so later files in this batch are checked against it;
        # its "id" is filled in once the save finishes.
        dedup.add(record)
        pending_saves.append((idx, record))

    # --- 4. save in parallel ----------------------------------------- #
    saved_list = await asyncio.gather(
        *(asyncio.to_thread(save, dict(record)) for _, record in pending_saves),
        return_exceptions=True,
    )
    for (idx, record), saved in zip(pending_saves, saved_list):
        if isinstance(saved, BaseException):
            logger.error("Failed to save %r: %s", results[idx]["file_name"], saved)
            results[idx]["error"] = f"שמירת המועמד נכשלה: {saved}"
            continue
        record["id"] = saved.get("id")
        results[idx].update(success=True, candidate=saved)

    for idx, field, existing in duplicates:
        results[idx].update(
            duplicate=True,
            duplicate_of_id=existing.get("id"),
            error=duplicate_message(field, existing),
        )

    return results


def _result(file_name: str) -> dict:
    return {
        "file_name": file_name,
        "success": False,
        "candidate": None,
        "error": None,
        "duplicate": False,
        "duplicate_of_id": None,
    }


def describe_duplicate(field: str, existing: dict) -> tuple[str, str, str]:
    """(display name, Hebrew field label, matched value) for duplicate messages."""
    name = " ".join(
        p for p in (existing.get("full_name"), existing.get("family_name")) if p
    ) or "ללא שם"
    label = "אותה כתובת מייל" if field == "email" else "אותו מספר טלפון"
    value = existing.get("email") if field == "email" else existing.get("phone")
    return name, label, value or ""
