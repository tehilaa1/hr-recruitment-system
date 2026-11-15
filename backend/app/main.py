from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import get_firestore_service
from app.routers import candidates, jobs, maternity, search, talent_pool, users
from app.security import require_member

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HR Recruitment Management System",
    description="SaaS backend for managing job positions and candidate pipelines",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the frontend read the download filename of the Excel export
    expose_headers=["Content-Disposition"],
)

# All data routers require an authenticated, authorized user (see app/security.py).
# Only /health is public.
_members_only = [Depends(require_member)]

app.include_router(jobs.router, dependencies=_members_only)
app.include_router(candidates.router, dependencies=_members_only)
app.include_router(search.router, dependencies=_members_only)
app.include_router(maternity.router, dependencies=_members_only)
app.include_router(talent_pool.router, dependencies=_members_only)

# Auth/users routers enforce their own rules (any member for /me, admin for /api/users)
app.include_router(users.auth_router)
app.include_router(users.router)


_firebase_error: str | None = None


@app.on_event("startup")
def _check_firebase() -> None:
    """Initialize Firebase at boot so missing credentials show up in the logs immediately."""
    global _firebase_error
    try:
        get_firestore_service()
        logger.info("Firebase initialized")
    except Exception as exc:  # keep serving /health so the problem is diagnosable
        _firebase_error = f"{type(exc).__name__}: {exc}"
        logger.error("Firebase initialization failed — data endpoints will return 500: %s", exc)
    logger.info("CORS allowed origins: %s", settings.CORS_ORIGINS)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok" if _firebase_error is None else "degraded",
        "firebase": "ok" if _firebase_error is None else "not configured",
    }
