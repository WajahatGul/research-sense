"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app when its dist folder is present (single-image
    deploys like a Hugging Face Docker Space). A catch-all returns index.html
    so client-side routes (/library, /portal, ...) work on refresh/deep-link.
    In local dev the dist folder is absent, so this is a no-op and the Vite
    dev server serves the frontend instead."""
    dist = Path(os.getenv(
        "FRONTEND_DIST",
        Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    index = dist / "index.html"
    if not index.is_file():
        return

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # /api/* and /docs are matched by earlier routes; this only handles
        # frontend paths. Serve a real static file when it exists, else the
        # SPA entry point.
        candidate = (dist / full_path).resolve()
        if str(candidate).startswith(str(dist.resolve())) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
