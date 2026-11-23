from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Local dev frontends — always allowed so `npm run dev` works against any backend.
# backend/ — so relative credential paths work no matter which directory uvicorn starts from
_BACKEND_DIR = Path(__file__).resolve().parents[1]
# Where Render mounts Secret Files
_RENDER_SECRETS_DIR = Path("/etc/secrets")

_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: str = "firebase_credentials.json"
    # Full service-account JSON (raw or base64) — easiest option on Render/hosts
    # where you can't ship a file. Takes precedence over the path settings.
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None

    # Primary model — confirmed stable for "new user" API keys.
    # Override via GEMINI_MODEL= in env.
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # Tried in order when the primary returns 503 or 404.
    # Set GEMINI_FALLBACK_MODELS=[] in env to disable fallbacks.
    GEMINI_FALLBACK_MODELS: List[str] = Field(
        default=["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
    )

    # Max retries on the same model before moving to the next one.
    GEMINI_RETRIES_PER_MODEL: int = 2

    # How many CVs are parsed in parallel per process (keeps batches under rate limits).
    GEMINI_MAX_CONCURRENCY: int = 4

    # --- SMS verification codes (password reset) ---
    # "console": simulation — codes are only written to the server log.
    # "twilio":  real SMS via Twilio (needs the three TWILIO_* values).
    SMS_PROVIDER: Literal["console", "twilio"] = "console"
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None  # E.164 number or Messaging Service SID ("MG…")
    # Testing only: the API also returns the code to the browser. NEVER enable in production.
    SMS_DEV_MODE: bool = False

    # --- Public demo workspace (see scripts/seed_demo_data.py) ---
    # The demo account lives in its own isolated tenant. Its password is shared
    # publicly (the login page's demo button), so the tenant holds sample data only.
    DEMO_EMAIL: str = "demo@hiretrack.app"
    DEMO_PASSWORD: Optional[str] = None  # only needed by the seed script / reset endpoint
    DEMO_TENANT_ID: str = "demo"
    # Free-tier protection for the demo tenant only
    DEMO_AI_DAILY_LIMIT: int = 20           # Gemini calls (CV parses + pool matching) per day
    DEMO_MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024
    DEMO_MAX_FILES_PER_UPLOAD: int = 5
    DEMO_MAX_RECORDS: int = 150             # per collection (jobs, candidates, pool, maternity)

    # Accepts a JSON list or a comma-separated string, e.g.
    # CORS_ORIGINS=https://my-frontend.onrender.com,https://hr.example.com
    # Local dev origins are always added on top.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default_factory=list)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: Union[str, List[str], None]) -> List[str]:
        if v is None:
            items: List[str] = []
        elif isinstance(v, str):
            v = v.strip()
            items = json.loads(v) if v.startswith("[") else v.split(",")
        else:
            items = list(v)
        origins = [o.strip().rstrip("/") for o in items if o and o.strip()]
        return list(dict.fromkeys(origins + _DEV_ORIGINS))

    model_config = SettingsConfigDict(
        env_file=["env.", ".env"],
        env_file_encoding="utf-8",
    )

    @property
    def firebase_credentials(self) -> Union[dict, str]:
        """Service-account info as a dict (from FIREBASE_CREDENTIALS_JSON) or a file path."""
        raw = (self.FIREBASE_CREDENTIALS_JSON or "").strip()
        if raw:
            if not raw.startswith("{"):
                try:
                    raw = base64.b64decode(raw).decode("utf-8")
                except Exception as exc:
                    raise ValueError(
                        "FIREBASE_CREDENTIALS_JSON is neither JSON nor valid base64"
                    ) from exc
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {exc}") from exc
        return _resolve_credentials_path(
            self.GOOGLE_APPLICATION_CREDENTIALS or self.FIREBASE_CREDENTIALS_PATH
        )


def _resolve_credentials_path(configured: str) -> str:
    """Find the service-account file: as given (absolute or relative to the CWD),
    relative to backend/, or as a Render Secret File in /etc/secrets/.
    Returns the configured value unchanged if none exist (the caller logs the error)."""
    path = Path(configured).expanduser()
    candidates = [path] if path.is_absolute() else [path, _BACKEND_DIR / path]
    candidates.append(_RENDER_SECRETS_DIR / path.name)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return configured


@lru_cache()
def get_settings() -> Settings:
    return Settings()
