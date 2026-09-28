"""SQLite store for mutable data: faculty accounts, uploads, refresh log.

The scraped research corpus is read-only JSON; accounts and uploads change at
runtime and need ACID writes, so they live in SQLite (stdlib, zero cost).
Connections are opened per operation, which is thread-safe and plenty fast at
this scale.
"""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path

from app.core.db import connect

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
    uploaded_at   TEXT NOT NULL,
    submission_id INTEGER
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
CREATE TABLE IF NOT EXISTS claims (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid_id      TEXT NOT NULL,
    researcher_id INTEGER NOT NULL,
    password_hash TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending',
    submitted_at  TEXT NOT NULL,
    reviewed_at   TEXT,
    note          TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    weak_password INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    created_by    TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT NOT NULL,
    actor  TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS corrections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    researcher_id INTEGER NOT NULL,
    payload_json  TEXT NOT NULL,
    note          TEXT,
    raised_by     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    submitted_at  TEXT NOT NULL,
    reviewed_at   TEXT,
    review_note   TEXT
);
CREATE TABLE IF NOT EXISTS submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    researcher_id INTEGER NOT NULL,
    title         TEXT NOT NULL,
    record_json   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    submitted_at  TEXT NOT NULL,
    reviewed_at   TEXT,
    note          TEXT
);
-- What people do, counted without knowing who they are: `visitor` is a
-- random id the browser made up, never an IP, account or name.
CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    at       TEXT NOT NULL,
    day      TEXT NOT NULL,
    kind     TEXT NOT NULL,
    visitor  TEXT NOT NULL DEFAULT '',
    detail   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS events_kind_day ON events (kind, day);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class AccountStore:
    _instance: AccountStore | None = None

    def __init__(self) -> None:
        with self._connect() as con:
            con.executescript(_SCHEMA)
            self._migrate(con)

    @classmethod
    def instance(cls) -> AccountStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _migrate(self, con: sqlite3.Connection) -> None:
        """Idempotent additive migrations for databases created before a
        schema change. `CREATE TABLE IF NOT EXISTS` in _SCHEMA never alters
        an existing table, so new nullable columns are added here."""
        cols = {row["name"] for row in con.execute("PRAGMA table_info(uploads)")}
        if "submission_id" not in cols:
            con.execute("ALTER TABLE uploads ADD COLUMN submission_id INTEGER")

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        # Read DB_PATH at call time so tests can point the store elsewhere.
        return connect(DB_PATH)

    # --- accounts ---
    def create_account(
        self, orcid_id: str, researcher_id: int, password_hash: str
    ) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO accounts (orcid_id, researcher_id, password_hash,"
                " created_at) VALUES (?, ?, ?, ?)",
                (orcid_id, researcher_id, password_hash, _now()),
            )

    def get_account(self, orcid_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM accounts WHERE orcid_id = ?", (orcid_id,)
            ).fetchone()
        return dict(row) if row else None

    def account_for_researcher(self, researcher_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM accounts WHERE researcher_id = ?", (researcher_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_accounts(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT orcid_id, researcher_id, active, created_at "
                "FROM accounts ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def set_active(self, orcid_id: str, active: bool) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE accounts SET active = ? WHERE orcid_id = ?",
                (1 if active else 0, orcid_id),
            )

    def claimed_researcher_ids(self) -> set[int]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT researcher_id FROM accounts WHERE active = 1"
            ).fetchall()
        return {r["researcher_id"] for r in rows}

    # --- profile claims (admin approval for claims ORCID did not prove) ---
    # A claim is not an account. Several people may claim one profile while
    # they wait; approving one creates the account and turns the rest down,
    # so a false claim cannot lock the real owner out.
    def create_claim(
        self, orcid_id: str, researcher_id: int, password_hash: str, evidence_json: str
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO claims (orcid_id, researcher_id, password_hash,"
                " evidence_json, submitted_at) VALUES (?, ?, ?, ?, ?)",
                (orcid_id, researcher_id, password_hash, evidence_json, _now()),
            )
            return int(cur.lastrowid)

    def get_claim(self, claim_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return dict(row) if row else None

    def pending_claims(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM claims WHERE status = 'pending' ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_claim_for_orcid(self, orcid_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM claims WHERE orcid_id = ? ORDER BY id DESC LIMIT 1",
                (orcid_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_claim_status(self, claim_id: int, status: str, note: str | None = None) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE claims SET status = ?, reviewed_at = ?, note = ? WHERE id = ?",
                (status, _now(), note, claim_id),
            )

    def reject_pending_claims_for(self, researcher_id: int, note: str) -> int:
        """Turn down every claim still waiting on this profile."""
        with self._connect() as con:
            cur = con.execute(
                "UPDATE claims SET status = 'rejected', reviewed_at = ?, note = ?"
                " WHERE researcher_id = ? AND status = 'pending'",
                (_now(), note, researcher_id),
            )
            return cur.rowcount

    # --- administrators ---
    def count_admins(self) -> int:
        with self._connect() as con:
            return con.execute("SELECT COUNT(*) AS n FROM admins").fetchone()["n"]

    def get_admin(self, username: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM admins WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def list_admins(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT username, active, weak_password, created_at, created_by"
                " FROM admins ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def create_admin(
        self, username: str, password_hash: str, weak: bool, created_by: str | None
    ) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO admins (username, password_hash, weak_password,"
                " created_at, created_by) VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, 1 if weak else 0, _now(), created_by),
            )

    def set_admin_active(self, username: str, active: bool) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE admins SET active = ? WHERE username = ?",
                (1 if active else 0, username),
            )

    def set_admin_password(self, username: str, password_hash: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE admins SET password_hash = ?, weak_password = 0 WHERE username = ?",
                (password_hash, username),
            )

    # --- audit log: append-only. There is deliberately no update or delete. ---
    def record(self, actor: str, action: str, target: str = "", detail: str = "") -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO audit_log (at, actor, action, target, detail)"
                " VALUES (?, ?, ?, ?, ?)",
                (_now(), actor, action, target, detail[:500]),
            )

    def recent_activity(self, limit: int = 50) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- record corrections (see app/services/identity_service.py) ---
    def create_correction(
        self, kind: str, researcher_id: int, payload_json: str, note: str, raised_by: str
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO corrections (kind, researcher_id, payload_json, note,"
                " raised_by, submitted_at) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, researcher_id, payload_json, note, raised_by, _now()),
            )
            return int(cur.lastrowid)

    def get_correction(self, correction_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM corrections WHERE id = ?", (correction_id,)
            ).fetchone()
        return dict(row) if row else None

    def pending_corrections(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM corrections WHERE status = 'pending' ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def corrections_for(self, researcher_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM corrections WHERE researcher_id = ? ORDER BY id DESC",
                (researcher_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_correction_status(
        self, correction_id: int, status: str, review_note: str | None = None
    ) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE corrections SET status = ?, reviewed_at = ?, review_note = ?"
                " WHERE id = ?",
                (status, _now(), review_note, correction_id),
            )

    # --- uploads ---
    def record_upload(
        self,
        researcher_id: int,
        title: str,
        filename: str,
        submission_id: int | None = None,
    ) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO uploads (researcher_id, title, filename,"
                " uploaded_at, submission_id) VALUES (?, ?, ?, ?, ?)",
                (researcher_id, title, filename, _now(), submission_id),
            )

    def uploads_for(self, researcher_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT title, filename, uploaded_at FROM uploads "
                "WHERE researcher_id = ? ORDER BY id DESC",
                (researcher_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def approved_uploads(self) -> list[dict]:
        """Uploads eligible for a full index rebuild: those with no linked
        submission (pre-approval-era rows, before the review gate existed —
        treated as already approved) plus those whose linked submission was
        actually approved. Pending and rejected uploads are excluded so
        scripts.build_index never indexes an unreviewed or rejected paper."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT u.researcher_id, u.title, u.filename FROM uploads u "
                "LEFT JOIN submissions s ON u.submission_id = s.id "
                "WHERE u.submission_id IS NULL OR s.status = 'approved' "
                "ORDER BY u.id"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_upload_for_submission(self, submission_id: int) -> None:
        """Remove the uploads row linked to a rejected submission."""
        with self._connect() as con:
            con.execute("DELETE FROM uploads WHERE submission_id = ?", (submission_id,))

    # --- paper submissions (admin approval workflow) ---
    def create_submission(
        self, kind: str, researcher_id: int, title: str, record_json: str
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO submissions (kind, researcher_id, title,"
                " record_json, submitted_at) VALUES (?, ?, ?, ?, ?)",
                (kind, researcher_id, title, record_json, _now()),
            )
            return int(cur.lastrowid)

    def get_submission(self, sub_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM submissions WHERE id = ?", (sub_id,)
            ).fetchone()
        return dict(row) if row else None

    def pending_submissions(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM submissions WHERE status = 'pending' ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def set_submission_status(
        self, sub_id: int, status: str, note: str | None = None
    ) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE submissions SET status = ?, reviewed_at = ?, note = ?"
                " WHERE id = ?",
                (status, _now(), note, sub_id),
            )

    def submissions_for(self, researcher_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, kind, title, status, submitted_at, reviewed_at,"
                " note FROM submissions WHERE researcher_id = ?"
                " ORDER BY id DESC",
                (researcher_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- meta / refresh ---
    def jwt_secret(self) -> str:
        with self._connect() as con:
            row = con.execute(
                "SELECT value FROM meta WHERE key = 'jwt_secret'"
            ).fetchone()
            if row:
                return row["value"]
            secret = secrets.token_hex(32)
            con.execute(
                "INSERT INTO meta (key, value) VALUES ('jwt_secret', ?)", (secret,)
            )
            return secret

    def last_refresh(self) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM refresh_log WHERE status = 'ok' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def start_refresh(self) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO refresh_log (started_at, status) VALUES (?, 'running')",
                (_now(),),
            )
            return int(cur.lastrowid)

    def finish_refresh(self, run_id: int, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE refresh_log SET finished_at = ?, status = ? WHERE id = ?",
                (_now(), status, run_id),
            )
