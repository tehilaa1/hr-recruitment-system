from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.firestore_service import FirestoreService
from app.services.gemini_service import GeminiService


@lru_cache()
def get_firestore_service() -> FirestoreService:
    settings = get_settings()
    return FirestoreService(settings.firebase_credentials)


@lru_cache()
def get_gemini_service() -> GeminiService:
    settings = get_settings()
    return GeminiService(
        api_key=settings.GEMINI_API_KEY,
        primary_model=settings.GEMINI_MODEL,
        fallback_models=settings.GEMINI_FALLBACK_MODELS,
        retries_per_model=settings.GEMINI_RETRIES_PER_MODEL,
        max_concurrency=settings.GEMINI_MAX_CONCURRENCY,
    )
