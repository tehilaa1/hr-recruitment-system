from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: str = "firebase_credentials.json"

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

    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    model_config = SettingsConfigDict(
        env_file=["env.", ".env"],
        env_file_encoding="utf-8",
    )

    @property
    def firebase_credentials(self) -> str:
        return self.GOOGLE_APPLICATION_CREDENTIALS or self.FIREBASE_CREDENTIALS_PATH


@lru_cache()
def get_settings() -> Settings:
    return Settings()
