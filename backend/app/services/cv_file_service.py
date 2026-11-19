"""Original CV files kept with candidate records (pure functions, no I/O).

The uploaded file is stored next to the record it was parsed into (a job
candidate or a talent-pool entry): metadata in the record's ``cv_file`` field,
raw bytes in a ``cv_chunks`` subcollection (see FirestoreService).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Response, UploadFile
from fastapi import status as http_status

from app.services.invoice_service import inline_disposition

# One Firestore batch (record + chunks) must stay under the 10 MiB request limit
CV_MAX_BYTES = 8 * 1024 * 1024

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOC = "application/msword"

# The only types a CV is ever served as (never text/html etc., since the
# frontend opens the file from a same-origin blob: URL)
CV_CONTENT_TYPES: dict[str, str] = {
    PDF: ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    DOCX: ".docx",
    DOC: ".doc",
}

# Same list as UploadBox's ACCEPTED in the frontend (plus .webp)
CV_UPLOAD_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "docx", "doc"}


@dataclass(frozen=True)
class CvFile:
    meta: dict  # {"file_name", "content_type", "size"}
    data: bytes


def detect_cv_content_type(data: bytes, file_name: str = "") -> Optional[str]:
    """The file's real type from its first bytes; None if it isn't a supported CV format.

    The browser-supplied MIME type is never trusted. Word files are containers
    (ZIP / OLE), so the extension only decides between .docx and .doc.
    """
    head = data[:1024]
    if head.startswith(b"%PDF-") or b"%PDF-" in head:
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if head.startswith(b"PK\x03\x04") and ext == "docx":
        return DOCX
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") and ext == "doc":
        return DOC
    return None


def cv_file_name(name: Optional[str], content_type: str) -> str:
    """Display/download name: no path parts or control characters, extension matching the content."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(c for c in unicodedata.normalize("NFC", base) if unicodedata.category(c)[0] != "C")
    base = re.sub(r"\s+", " ", base).strip().strip(".")
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return (stem[:120].strip() or "cv") + CV_CONTENT_TYPES[content_type]


def build_cv_file(file_name: Optional[str], data: bytes) -> Optional[CvFile]:
    """A storable CV, or None if the file is empty, too large or not a supported type."""
    if not data or len(data) > CV_MAX_BYTES:
        return None
    content_type = detect_cv_content_type(data, file_name or "")
    if content_type is None:
        return None
    meta = {
        "file_name": cv_file_name(file_name, content_type),
        "content_type": content_type,
        "size": len(data),
    }
    return CvFile(meta=meta, data=data)


def cv_info(record: dict) -> Optional[dict]:
    """The record's public CV metadata, or None if no file was stored."""
    meta = record.get("cv_file")
    if not isinstance(meta, dict) or meta.get("content_type") not in CV_CONTENT_TYPES:
        return None
    return {
        "file_name": str(meta.get("file_name") or "cv"),
        "content_type": meta["content_type"],
        "size": int(meta.get("size") or 0),
    }


# ------------------------------------------------------------------ #
# HTTP helpers shared by the job-candidate and talent-pool routers     #
# ------------------------------------------------------------------ #

NO_CV = "לא נשמר קובץ קורות חיים עבור מועמד זה"


def cv_response(cv: Optional[CvFile]) -> Response:
    """The stored CV, opened inline by the browser (404 if there is none)."""
    if cv is None or cv.meta.get("content_type") not in CV_CONTENT_TYPES:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, NO_CV)
    return Response(
        content=cv.data,
        media_type=cv.meta["content_type"],
        headers={
            "Content-Disposition": inline_disposition(cv.meta.get("file_name") or "cv.pdf", "cv"),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


async def read_cv_upload(file: UploadFile) -> CvFile:
    """Validate an uploaded CV for attaching to an existing record."""
    data = await file.read(CV_MAX_BYTES + 1)
    if len(data) > CV_MAX_BYTES:
        raise HTTPException(
            http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"הקובץ גדול מדי (עד {CV_MAX_BYTES // (1024 * 1024)}MB)",
        )
    if not data:
        raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_ENTITY, "הקובץ ריק")
    cv = build_cv_file(file.filename, data)
    if cv is None:
        raise HTTPException(
            http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "סוג קובץ לא נתמך – PDF, Word (.docx/.doc) או תמונה (PNG, JPG, WEBP)",
        )
    return cv
