from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import candidates, jobs, maternity, search, users
from app.security import require_member

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

settings = get_settings()

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

# Auth/users routers enforce their own rules (any member for /me, admin for /api/users)
app.include_router(users.auth_router)
app.include_router(users.router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
