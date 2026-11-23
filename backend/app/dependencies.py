from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.firestore_service import FirestoreService
from app.services.gemini_service import GeminiService
from app.services.sms_service import SmsSender, build_sms_sender


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


@lru_cache()
def get_sms_sender() -> SmsSender:
    return build_sms_sender(get_settings())


def get_password_reset_service():
    # Imported here so auth_service (firebase_admin.auth) loads only when needed
    from app.services import auth_service
    from app.services.password_reset_service import PasswordResetService

    return PasswordResetService(
        store=get_firestore_service(),
        sms=get_sms_sender(),
        set_password=auth_service.set_password,
        revoke_sessions=auth_service.revoke_sessions,
        dev_mode=get_settings().SMS_DEV_MODE,
        locked_tenant_ids=(get_settings().DEMO_TENANT_ID,),
    )
