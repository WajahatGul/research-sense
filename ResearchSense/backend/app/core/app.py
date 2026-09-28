"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.health import check as health_check
from app.core.security import workspace_from_token
from app.repositories.loader import set_workspace
from app.routers import (
    admin,
    analytics,
    auth,
    departments,
    chat,
    library,
    papers,
    projects,
    publications,
    researchers,
    organisation,
    stats,
    suggest,
    topics,
    workspace,
)
from app.services.refresh_service import weekly_refresh_loop

log = logging.getLogger("researchsense")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

# The trace middleware below logs each request once, with its ID and
# duration but without the query string (which holds what people searched
# for). Uvicorn's own access log would repeat every line and print the query
# string, so it is switched off here, whichever command starts the server.
logging.getLogger("uvicorn.access").disabled = True

# A caller may pass its own ID to correlate across services, but only a
# short, plain token: anything else could forge or corrupt log lines.
_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")


def _warm_search_indexes() -> None:
    """Tokenise the public corpus once at startup (~1 s) so the first
    visitor to search after a restart does not pay for it."""
    from app.repositories.mock.publications import MockPublicationRepository
    from app.repositories.mock.researchers import MockResearcherRepository

    try:
        for repo in (MockResearcherRepository(), MockPublicationRepository()):
            repo.list(query="warm")  # per-record tokens
            repo.suggest("warm")  # spelling-correction vocabulary
    except Exception:  # warming is an optimisation, never a startup failure
        log.exception("search index warm-up failed")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = asyncio.create_task(weekly_refresh_loop())
    warm = asyncio.create_task(asyncio.to_thread(_warm_search_indexes))
    yield
    task.cancel()
    warm.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def scope_to_workspace(request, call_next):
        """Pin the request to the caller's workspace before anything reads data.

        A signed-in institution's token carries its workspace; anyone else (an
        anonymous visitor, or a Bahria ORCID login) gets the bundled demo
        corpus, so the public portal is unchanged.
        """
        header = request.headers.get("authorization") or ""
        raw = header[7:] if header.lower().startswith("bearer ") else None
        set_workspace(workspace_from_token(raw))
        return await call_next(request)

    for module in (
        stats,
        researchers,
        publications,
        topics,
        projects,
        chat,
        auth,
        papers,
        admin,
        analytics,
        library,
        workspace,
        suggest,
        organisation,
        departments,
    ):
        app.include_router(module.router)

    @app.middleware("http")
    async def trace(request, call_next):
        """Give every request an ID and a duration, in the response and the log.

        Added last so it wraps everything: the time measured is the time the
        caller waited. Only the path is logged — query strings carry what
        people searched for, which does not belong in server logs.
        """
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("%s %s %s failed", rid, request.method, request.url.path)
            raise
        ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
        log.info(
            "%s %s %s %d %.1fms",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response

    @app.get("/api/health", tags=["health"])
    def health() -> JSONResponse:
        serving, report = health_check()
        report["service"] = settings.app_name
        return JSONResponse(report, status_code=200 if serving else 503)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app when its dist folder is present (single-image
    deploys like a Hugging Face Docker Space). A catch-all returns index.html
    so client-side routes (/library, /portal, ...) work on refresh/deep-link.
    In local dev the dist folder is absent, so this is a no-op and the Vite
    dev server serves the frontend instead."""
    dist = Path(
        os.getenv(
            "FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"
        )
    )
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
