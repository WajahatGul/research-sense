"""Data refresh: re-fetch publications from OpenAlex and rebuild the RAG index.

Runs weekly from a background task in the app lifespan, and on demand from the
admin API. Every run is recorded in SQLite; failures are logged and recorded,
never swallowed.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from app.repositories.accounts import AccountStore
from app.services.rag.retriever import Retriever

log = logging.getLogger("researchsense.refresh")

REFRESH_EVERY = timedelta(days=7)
CHECK_EVERY_SECONDS = 24 * 3600
_lock = threading.Lock()


def run_refresh() -> str:
    """Fetch fresh publications and rebuild the index. Returns final status."""
    if not _lock.acquire(blocking=False):
        return "already-running"
    store = AccountStore.instance()
    run_id = store.start_refresh()
    try:
        from scripts import build_index, fetch_publications

        log.info("refresh: fetching publications from OpenAlex")
        fetch_publications.main()
        log.info("refresh: rebuilding RAG index")
        build_index.main()
        Retriever.reset()
        store.finish_refresh(run_id, "ok")
        log.info("refresh: done")
        return "ok"
    except Exception as exc:  # noqa: BLE001 - record and surface, don't hide
        store.finish_refresh(run_id, f"error: {exc}")
        log.exception("refresh failed")
        return f"error: {exc}"
    finally:
        _lock.release()


def is_due() -> bool:
    last = AccountStore.instance().last_refresh()
    if last is None:
        return False  # first fill is done by the setup scripts, not the app
    finished = datetime.fromisoformat(last["finished_at"]).replace(
        tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - finished > REFRESH_EVERY


async def weekly_refresh_loop() -> None:
    """Lifespan task: check daily, refresh when a week has passed."""
    while True:
        await asyncio.sleep(CHECK_EVERY_SECONDS)
        try:
            if is_due():
                log.info("weekly refresh is due, starting")
                await asyncio.to_thread(run_refresh)
        except Exception:  # noqa: BLE001 - the loop itself must survive
            log.exception("weekly refresh loop error")
