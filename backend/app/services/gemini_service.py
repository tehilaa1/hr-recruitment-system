from __future__ import annotations

import json
import logging
import time
from io import BytesIO

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Public exception — caught in the router and surfaced per-file       #
# ------------------------------------------------------------------ #

class GeminiParseError(Exception):
    """Raised when every model in the fallback chain fails."""


# ------------------------------------------------------------------ #
# Prompt & constants                                                  #
# ------------------------------------------------------------------ #

_PROMPT = """You are an expert CV/resume parser. Extract the following fields from the provided resume document and return ONLY a valid JSON object — no explanation, no markdown, no code blocks.

Required JSON format:
{
  "full_name": "",
  "family_name": "",
  "phone": "",
  "email": "",
  "address": "",
  "profession": "",
  "years_of_experience": 0
}

Field rules:
- full_name: given/first name only
- family_name: family/last name only
- years_of_experience: integer — calculate from work history date ranges if not stated explicitly; use 0 if unknown
- For any string field that cannot be determined, use an empty string ""
- The CV may be in Hebrew, English, or a mix — handle all cases correctly
"""

_IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_PDF_MIME_TYPE = "application/pdf"
_DOCX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

_DEFAULTS: dict = {
    "full_name": "",
    "family_name": "",
    "phone": "",
    "email": "",
    "address": "",
    "profession": "",
    "years_of_experience": 0,
}

_EXT_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}


# ------------------------------------------------------------------ #
# Service                                                             #
# ------------------------------------------------------------------ #

class GeminiService:
    def __init__(
        self,
        api_key: str,
        primary_model: str = "gemini-3.5-flash",
        fallback_models: list[str] | None = None,
        retries_per_model: int = 2,
    ) -> None:
        self.client = genai.Client(api_key=api_key)
        self._retries_per_model = retries_per_model

        # Build ordered, deduplicated model chain.
        chain: list[str] = [primary_model]
        for m in (fallback_models or []):
            if m not in chain:
                chain.append(m)
        self._model_chain = chain

        logger.info(
            "Gemini service ready. Model chain: %s",
            " → ".join(self._model_chain),
        )

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #

    def parse_cv(self, file_bytes: bytes, file_name: str, content_type: str) -> dict:
        mime = self._resolve_mime(content_type, _ext(file_name))

        if mime in _IMAGE_MIME_TYPES or mime == _PDF_MIME_TYPE:
            contents: list = [
                types.Part.from_bytes(data=file_bytes, mime_type=mime),
                _PROMPT,
            ]
        elif mime in _DOCX_MIME_TYPES or _ext(file_name) in ("docx", "doc"):
            text = self._extract_docx_text(file_bytes)
            contents = [f"{_PROMPT}\n\nCV text content:\n{text}"]
        else:
            raise GeminiParseError(
                f"סוג הקובץ אינו נתמך: {file_name!r} (MIME: {mime!r})"
            )

        raw = self._call_with_retry(contents, file_name)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Non-JSON response for %r: %.200s", file_name, raw)
            raise GeminiParseError(
                f"ה-AI החזיר תשובה לא תקינה עבור {file_name}. נסה שנית."
            ) from exc

        return self._clean(parsed)

    # ------------------------------------------------------------------ #
    # Retry + fallback core                                                #
    # ------------------------------------------------------------------ #

    def _call_with_retry(self, contents: list, file_name: str) -> str:
        """
        Try each model in the chain in order.
        On 503 (server overloaded): retry up to `retries_per_model` times with
        exponential back-off (1 s, 2 s, …) before moving to the next model.
        On 404 / "no longer available": skip to the next model immediately.
        Any other client error (bad auth, bad request): re-raise immediately.
        """
        last_exc: Exception | None = None

        for model in self._model_chain:
            for attempt in range(self._retries_per_model + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )
                    if model != self._model_chain[0]:
                        logger.info(
                            "File %r parsed with fallback model %r", file_name, model
                        )
                    return response.text

                except ServerError as exc:
                    # 5xx — transient overload; back off then retry.
                    last_exc = exc
                    if attempt < self._retries_per_model:
                        wait = 2 ** attempt          # 1 s → 2 s → …
                        logger.warning(
                            "Model %r returned 503 for %r (attempt %d/%d) — "
                            "retrying in %ds",
                            model,
                            file_name,
                            attempt + 1,
                            self._retries_per_model + 1,
                            wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.warning(
                            "Model %r exhausted %d retries for %r — "
                            "trying next model",
                            model,
                            self._retries_per_model + 1,
                            file_name,
                        )

                except ClientError as exc:
                    last_exc = exc
                    err_text = str(exc)
                    if any(
                        marker in err_text
                        for marker in ("404", "NOT_FOUND", "no longer available", "new users")
                    ):
                        # This model is unavailable for this API key — skip it.
                        logger.warning(
                            "Model %r not available for this API key — skipping", model
                        )
                        break  # next model, no retry
                    # Auth failure, quota, bad request, etc. — escalate immediately.
                    logger.error(
                        "Non-recoverable Gemini error for %r: %s", file_name, err_text
                    )
                    raise GeminiParseError(
                        f"שגיאת AI: {err_text[:120]}"
                    ) from exc

        # Every model in the chain failed.
        raise GeminiParseError(
            "שרת ה-AI עמוס כרגע. אנא המתן מספר דקות ונסה שנית."
        ) from last_exc

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_mime(content_type: str, ext: str) -> str:
        if content_type and content_type not in (
            "application/octet-stream",
            "binary/octet-stream",
        ):
            return content_type.split(";")[0].strip().lower()
        return _EXT_TO_MIME.get(ext, content_type)

    @staticmethod
    def _extract_docx_text(file_bytes: bytes) -> str:
        import docx  # lazy import — only needed for Word files

        document = docx.Document(BytesIO(file_bytes))
        lines: list[str] = []

        for para in document.paragraphs:
            if para.text.strip():
                lines.append(para.text.strip())

        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    lines.append(row_text)

        return "\n".join(lines)

    @staticmethod
    def _clean(data: dict) -> dict:
        result: dict = dict(_DEFAULTS)
        for key in _DEFAULTS:
            val = data.get(key)
            if key == "years_of_experience":
                try:
                    result[key] = int(val) if val is not None else 0
                except (TypeError, ValueError):
                    result[key] = 0
            else:
                result[key] = str(val).strip() if val is not None else ""
        return result


# ------------------------------------------------------------------ #
# Module-level helper                                                  #
# ------------------------------------------------------------------ #

def _ext(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
