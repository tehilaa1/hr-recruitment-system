"""Invoice file handling for holiday expenses (pure functions, no I/O)."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import quote

from app.models.budget import INVOICE_CONTENT_TYPES

# Below Firestore's 1 MiB document limit, leaving room for the field name and metadata
CHUNK_BYTES = 900_000

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def detect_content_type(data: bytes) -> Optional[str]:
    """The file's real type from its first bytes; None if it isn't a PDF/PNG/JPEG.

    The browser-supplied MIME type and file extension are never trusted.
    """
    head = data[:1024]
    for signature, content_type in _SIGNATURES:
        if head.startswith(signature):
            return content_type
    # Some PDF writers put a few bytes (e.g. a BOM) before the header
    if b"%PDF-" in head:
        return "application/pdf"
    return None


def safe_file_name(name: Optional[str], content_type: str) -> str:
    """Display/download name: no path parts or control characters, extension matching the content."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(c for c in unicodedata.normalize("NFC", base) if unicodedata.category(c)[0] != "C")
    base = re.sub(r"\s+", " ", base).strip().strip(".")
    stem = base.rsplit(".", 1)[0] if "." in base else base
    stem = stem[:120].strip() or "invoice"
    return stem + INVOICE_CONTENT_TYPES[content_type]


def split_chunks(data: bytes, size: int = CHUNK_BYTES) -> list[bytes]:
    return [data[i:i + size] for i in range(0, len(data), size)] or [b""]


def inline_disposition(file_name: str) -> str:
    """Content-Disposition that opens in the browser and keeps a Hebrew name (RFC 5987)."""
    ascii_name = "".join(c if c.isascii() and c.isprintable() and c not in '"\\;' else "_" for c in file_name)
    stem, _, ext = ascii_name.rpartition(".")
    if not stem.strip("_ "):
        ascii_name = f"invoice.{ext}"
    return f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}"
