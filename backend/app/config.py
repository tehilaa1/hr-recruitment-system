from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Annotated, List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Local dev frontends — always allowed so `npm run dev` works against any backend.
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
        return self.GOOGLE_APPLICATION_CREDENTIALS or self.FIREBASE_CREDENTIALS_PATH


@lru_cache()
def get_settings() -> Settings:
    return Settings()
