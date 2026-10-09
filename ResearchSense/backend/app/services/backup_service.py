"""Backups of the accounts database, and a restore that is checked first.

The accounts database is the one thing ResearchSense cannot rebuild: the
corpus comes back from OpenAlex, but claims, corrections, uploaded papers,
administrators and the activity log exist nowhere else. It is copied once a
day (and on demand from the admin panel) with SQLite's online backup, which
is safe while the site is serving. Every copy is checked before it is kept,
and again before it is restored, and a restore first backs up the database
it replaces, so undoing a restore is another restore.

Backups sit beside the database unless RS_BACKUP_DIR names a folder on a
disk that outlives the server (on a host with a throwaway disk, same-disk
copies are lost with the database).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.repositories import accounts

log = logging.getLogger("researchsense.backup")

KEEP = 14
BACKUP_EVERY = timedelta(days=1)
CHECK_EVERY_SECONDS = 60 * 60
# The tables a usable accounts database must have.
REQUIRED = ("accounts", "claims", "submissions", "admins", "audit_log")
# Shown to admins as a count, so they can tell one copy from another.
COUNTED = ("accounts", "claims", "corrections", "submissions", "admins", "audit_log")
NAME = re.compile(r"^accounts-\d{8}-\d{6}(-[a-z-]+)?\.db$")


class BackupError(RuntimeError):
    """A backup could not be made, or is not safe to restore."""


def backup_dir() -> Path:
    configured = os.getenv("RS_BACKUP_DIR", "").strip()
    return Path(configured) if configured else accounts.DB_PATH.parent / "backups"


def inspect(path: Path) -> dict:
    """Check a database file; return its row counts or raise BackupError."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise BackupError(f"the copy is damaged ({ok})")
            tables = {
                r[0]
                for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = [t for t in REQUIRED if t not in tables]
            if missing:
                raise BackupError(f"the copy has no {', '.join(missing)} table")
            return {
                t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in COUNTED
                if t in tables
            }
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"not a readable database ({exc})") from exc


def _copy(source: Path, target: Path) -> None:
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def take(label: str = "") -> dict:
    """Back up the live database now; keep the newest KEEP copies."""
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    name = f"accounts-{stamp}{f'-{label}' if label else ''}.db"
    partial = folder / f"{name}.partial"
    _copy(accounts.DB_PATH, partial)
    try:
        counts = inspect(partial)
    except BackupError:
        partial.unlink(missing_ok=True)
        raise
    target = folder / name
    partial.replace(target)
    _prune(folder)
    log.info("backup: wrote %s", target)
    return _describe(target, counts)


def _prune(folder: Path) -> None:
    for old in sorted(folder.glob("accounts-*.db"), reverse=True)[KEEP:]:
        old.unlink(missing_ok=True)


def _describe(path: Path, counts: dict | None = None) -> dict:
    at = datetime.strptime(path.name[9:24], "%Y%m%d-%H%M%S").replace(tzinfo=UTC)
    return {
        "name": path.name,
        "at": at.isoformat(timespec="seconds"),
        "size": path.stat().st_size,
        "counts": counts if counts is not None else _safe_counts(path),
    }


def _safe_counts(path: Path) -> dict | None:
    try:
        return inspect(path)
    except BackupError:
        return None  # listed, but shown as unusable


def list_backups() -> list[dict]:
    folder = backup_dir()
    if not folder.exists():
        return []
    return [
        _describe(p)
        for p in sorted(folder.glob("accounts-*.db"), reverse=True)
        if NAME.match(p.name)
    ]


def restore(name: str) -> dict:
    """Replace the live database with a checked backup.

    The current database is backed up first (labelled before-restore), so a
    restore can itself be undone.
    """
    if not NAME.match(name):
        raise BackupError("no such backup")
    source = backup_dir() / name
    if not source.exists():
        raise BackupError("no such backup")
    counts = inspect(source)
    safety = take("before-restore")
    _copy(source, accounts.DB_PATH)
    log.warning(
        "backup: restored %s (previous state saved as %s)", name, safety["name"]
    )
    return {"restored": name, "counts": counts, "previous": safety["name"]}


def is_due() -> bool:
    latest = next(iter(list_backups()), None)
    if latest is None:
        return True
    return datetime.now(UTC) - datetime.fromisoformat(latest["at"]) > BACKUP_EVERY


async def daily_backup_loop() -> None:
    """Lifespan task: back up once a day."""
    # Let the app settle first (and keep short-lived test apps from copying
    # the real database).
    await asyncio.sleep(60)
    while True:
        try:
            if accounts.DB_PATH.exists() and is_due():
                await asyncio.to_thread(take)
        except Exception:  # noqa: BLE001 - the loop itself must survive
            log.exception("daily backup failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
