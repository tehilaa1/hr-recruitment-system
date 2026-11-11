from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import candidates, jobs, maternity, search

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

app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(search.router)
app.include_router(maternity.router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
