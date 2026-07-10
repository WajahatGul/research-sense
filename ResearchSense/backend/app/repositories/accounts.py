"""SQLite store for mutable data: faculty accounts, uploads, refresh log.

The scraped research corpus is read-only JSON; accounts and uploads change at
runtime and need ACID writes, so they live in SQLite (stdlib, zero cost).
Connections are opened per operation, which is thread-safe and plenty fast at
this scale.
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "researchsense.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    orcid_id      TEXT PRIMARY KEY,
    researcher_id INTEGER NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER NOT NULL,
    title         TEXT NOT NULL,
    filename      TEXT NOT NULL,
    uploaded_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AccountStore:
    _instance: "AccountStore | None" = None

    def __init__(self) -> None:
        with self._connect() as con:
            con.executescript(_SCHEMA)

    @classmethod
    def instance(cls) -> "AccountStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    # --- accounts ---
    def create_account(self, orcid_id: str, researcher_id: int,
                       password_hash: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO accounts (orcid_id, researcher_id, password_hash,"
                " created_at) VALUES (?, ?, ?, ?)",
                (orcid_id, researcher_id, password_hash, _now()))

    def get_account(self, orcid_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM accounts WHERE orcid_id = ?", (orcid_id,)).fetchone()
        return dict(row) if row else None

    def account_for_researcher(self, researcher_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM accounts WHERE researcher_id = ?",
                (researcher_id,)).fetchone()
        return dict(row) if row else None

    def list_accounts(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT orcid_id, researcher_id, active, created_at "
                "FROM accounts ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_active(self, orcid_id: str, active: bool) -> None:
        with self._connect() as con:
            con.execute("UPDATE accounts SET active = ? WHERE orcid_id = ?",
                        (1 if active else 0, orcid_id))

    def claimed_researcher_ids(self) -> set[int]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT researcher_id FROM accounts WHERE active = 1").fetchall()
        return {r["researcher_id"] for r in rows}

    # --- uploads ---
    def record_upload(self, researcher_id: int, title: str, filename: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO uploads (researcher_id, title, filename, uploaded_at)"
                " VALUES (?, ?, ?, ?)",
                (researcher_id, title, filename, _now()))

    def uploads_for(self, researcher_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT title, filename, uploaded_at FROM uploads "
                "WHERE researcher_id = ? ORDER BY id DESC",
                (researcher_id,)).fetchall()
        return [dict(r) for r in rows]

    # --- meta / refresh ---
    def jwt_secret(self) -> str:
        with self._connect() as con:
            row = con.execute(
                "SELECT value FROM meta WHERE key = 'jwt_secret'").fetchone()
            if row:
                return row["value"]
            secret = secrets.token_hex(32)
            con.execute("INSERT INTO meta (key, value) VALUES ('jwt_secret', ?)",
                        (secret,))
            return secret

    def last_refresh(self) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM refresh_log WHERE status = 'ok' "
                "ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def start_refresh(self) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO refresh_log (started_at, status) VALUES (?, 'running')",
                (_now(),))
            return int(cur.lastrowid)

    def finish_refresh(self, run_id: int, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE refresh_log SET finished_at = ?, status = ? WHERE id = ?",
                (_now(), status, run_id))
