"""FastAPI application factory."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    admin,
    analytics,
    auth,
    chat,
    library,
    papers,
    projects,
    publications,
    researchers,
    stats,
    topics,
)
from app.services.refresh_service import weekly_refresh_loop


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = asyncio.create_task(weekly_refresh_loop())
    yield
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version,
                  lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (stats, researchers, publications, topics, projects, chat,
                   auth, papers, admin, analytics, library):
        app.include_router(module.router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app
