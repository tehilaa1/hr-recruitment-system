from __future__ import annotations

import asyncio
import json
import logging
import re
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

# Second, narrow pass used only when the main parse returned no usable name.
_NAME_PROMPT = """The previous pass could not find the candidate's name in this CV/resume. Focus ONLY on finding the name of the person this CV belongs to.

Where to look, in order:
1. The document header / title area (often the largest text at the top)
2. The contact / personal details section (next to phone, email, address)
3. The email address local part (e.g. "dana.levi@..." suggests "Dana Levi") — use only as a last resort
4. A signature or footer

Return ONLY a valid JSON object — no explanation, no markdown:
{"full_name": "", "family_name": ""}

Rules:
- full_name: given/first name only; family_name: family/last name only
- Keep the name in the script it appears in (Hebrew stays Hebrew)
- Do NOT return company names, job titles, section headings or placeholders such as "לא ידוע" / "Unknown"
- If the name truly cannot be found, return empty strings
"""

_MATCH_PROMPT = """You are a senior Israeli HR recruiter. Rank the candidates from our talent pool by how well they fit the job below.

Job title: {job_title}
Job description:
{job_description}

Candidates (JSON list; "id" is our internal identifier):
{candidates_json}

Return ONLY a valid JSON object — no explanation, no markdown:
{{"matches": [{{"id": "", "score": 0, "match_reason": ""}}]}}

Rules:
- Include at most {limit} candidates, best fit first, and only those that are a reasonable fit (score >= 50). An empty list is a valid answer.
- score: integer 0-100
- match_reason: one or two short sentences in natural, professional Hebrew explaining specifically why this candidate fits this role — refer to their actual profession, experience and location versus the job's requirements. No generic praise.
- Use only ids that appear in the candidate list.
"""

# Values the model sometimes returns instead of leaving the name empty
_NAME_PLACEHOLDERS = {
    "", "-", "—", "n/a", "na", "none", "null", "unknown", "not found", "not specified",
    "candidate", "name", "full name",
    "לא ידוע", "לא צוין", "לא צויין", "לא נמצא", "אין", "ללא", "ללא שם", "שם", "מועמד", "מועמדת",
}

# How many candidates are sent to the model in one matching request
_MAX_POOL_FOR_MATCHING = 300

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
        max_concurrency: int = 4,
    ) -> None:
        self.client = genai.Client(api_key=api_key)
        self._retries_per_model = retries_per_model
        # Caps simultaneous CV parses so a large batch doesn't trip Gemini rate limits.
        # asyncio.Semaphore binds to the running loop lazily (Python 3.10+).
        self._parse_slots = asyncio.Semaphore(max(1, max_concurrency))

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

    async def parse_cv_async(
        self, file_bytes: bytes, file_name: str, content_type: str
    ) -> dict:
        """parse_cv off the event loop, limited to `max_concurrency` at a time.

        Callers can asyncio.gather() many of these to parse a batch in parallel.
        """
        async with self._parse_slots:
            return await asyncio.to_thread(self.parse_cv, file_bytes, file_name, content_type)

    def parse_cv(self, file_bytes: bytes, file_name: str, content_type: str) -> dict:
        document = self._document_parts(file_bytes, file_name, content_type)
        parsed = self._clean(self._generate_json(document + [_PROMPT], file_name))

        if is_missing_name(parsed["full_name"]):
            parsed.update(self._retry_name(document, file_name, parsed))
        return parsed

    def match_candidates(
        self,
        job_title: str,
        job_description: str,
        candidates: list[dict],
        limit: int = 5,
    ) -> list[dict]:
        """Rank talent-pool candidates for a job.

        Returns [{"id", "score", "match_reason"}], best first, containing only
        ids that exist in `candidates`.
        """
        if not candidates:
            return []

        pool = candidates[:_MAX_POOL_FOR_MATCHING]
        summary = [
            {
                "id": c["id"],
                "name": " ".join(
                    p for p in (c.get("full_name"), c.get("family_name")) if p
                ),
                "profession": c.get("profession", ""),
                "years_of_experience": c.get("years_of_experience", 0),
                "address": c.get("address", ""),
            }
            for c in pool
        ]
        prompt = _MATCH_PROMPT.format(
            job_title=job_title,
            job_description=job_description or "(no description provided)",
            candidates_json=json.dumps(summary, ensure_ascii=False),
            limit=limit,
        )
        data = self._generate_json([prompt], f"match:{job_title}", temperature=0.2)

        raw_matches = data.get("matches") if isinstance(data, dict) else data
        known_ids = {c["id"] for c in pool}
        results: list[dict] = []
        seen: set[str] = set()
        for m in raw_matches if isinstance(raw_matches, list) else []:
            if not isinstance(m, dict):
                continue
            cid = str(m.get("id") or "")
            reason = str(m.get("match_reason") or "").strip()
            if cid not in known_ids or cid in seen or not reason:
                continue
            try:
                score = max(0, min(100, int(m.get("score") or 0)))
            except (TypeError, ValueError):
                score = 0
            seen.add(cid)
            results.append({"id": cid, "score": score, "match_reason": reason})

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------ #
    # Parsing steps                                                        #
    # ------------------------------------------------------------------ #

    def _document_parts(
        self, file_bytes: bytes, file_name: str, content_type: str
    ) -> list:
        """The CV as Gemini content parts (file bytes, or extracted Word text)."""
        mime = self._resolve_mime(content_type, _ext(file_name))
        if mime in _IMAGE_MIME_TYPES or mime == _PDF_MIME_TYPE:
            return [types.Part.from_bytes(data=file_bytes, mime_type=mime)]
        if mime in _DOCX_MIME_TYPES or _ext(file_name) in ("docx", "doc"):
            return [f"CV text content:\n{self._extract_docx_text(file_bytes)}"]
        raise GeminiParseError(f"סוג הקובץ אינו נתמך: {file_name!r} (MIME: {mime!r})")

    def _generate_json(
        self, contents: list, file_name: str, temperature: float = 0.1
    ) -> dict | list:
        raw = self._call_with_retry(contents, file_name, temperature=temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Non-JSON response for %r: %.200s", file_name, raw)
            raise GeminiParseError(
                f"ה-AI החזיר תשובה לא תקינה עבור {file_name}. נסה שנית."
            ) from exc

    def _retry_name(self, document: list, file_name: str, parsed: dict) -> dict:
        """Targeted second pass for the name. Never fails the whole parse:
        on any error the original (empty) name is kept."""
        logger.info("No name found in %r — retrying with a name-only prompt", file_name)
        try:
            data = self._generate_json(document + [_NAME_PROMPT], file_name)
        except GeminiParseError as exc:
            logger.warning("Name retry failed for %r: %s", file_name, exc)
            return {"full_name": "", "family_name": parsed["family_name"]}

        if not isinstance(data, dict):
            data = {}
        full_name = _clean_str(data.get("full_name"))
        family_name = _clean_str(data.get("family_name"))
        if is_missing_name(full_name):
            logger.info("Name retry for %r found no name either", file_name)
            # Don't store a placeholder like "לא ידוע" as the name
            return {"full_name": "", "family_name": parsed["family_name"]}
        return {
            "full_name": full_name,
            "family_name": family_name
            if not is_missing_name(family_name)
            else parsed["family_name"],
        }

    # ------------------------------------------------------------------ #
    # Retry + fallback core                                                #
    # ------------------------------------------------------------------ #

    def _call_with_retry(
        self, contents: list, file_name: str, temperature: float = 0.1
    ) -> str:
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
                            temperature=temperature,
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
                result[key] = _clean_str(val)
        if is_missing_name(result["family_name"]):
            result["family_name"] = ""
        return result


# ------------------------------------------------------------------ #
# Module-level helpers                                                 #
# ------------------------------------------------------------------ #

def is_missing_name(value: object) -> bool:
    """True for empty names and for placeholders like "לא ידוע" / "Unknown"."""
    text = re.sub(r"[\s\"'()\[\].:]+", " ", str(value or "")).strip().lower()
    return text in _NAME_PLACEHOLDERS


def _clean_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _ext(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
