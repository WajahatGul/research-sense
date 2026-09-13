"""Workspaces: an institution's own space, created when someone signs up.

The bundled corpus (the public demo) is not a row here — it is the implicit
default. Every other institution gets a row, a folder of JSON files under
``data/workspaces/<id>/``, and an owner account identified by email. Bahria's
ORCID "claim a profile" flow is untouched and lives in ``accounts.py``.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import UTC, datetime

from app.repositories.accounts import DB_PATH
from app.repositories.loader import DEFAULT_WORKSPACE, save, workspace_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id     TEXT PRIMARY KEY,
    institution_name TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_accounts (
    email         TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    workspace_id  TEXT NOT NULL,
    researcher_id INTEGER NOT NULL,
    full_name     TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32] or "workspace"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class WorkspaceStore:
    _instance: WorkspaceStore | None = None

    def __init__(self) -> None:
        with self._connect() as con:
            con.executescript(_SCHEMA)

    @classmethod
    def instance(cls) -> WorkspaceStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    # --- accounts -----------------------------------------------------------

    def account_by_email(self, email: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM workspace_accounts WHERE email = ?", (email.lower(),)
            ).fetchone()
        return dict(row) if row else None

    def workspace(self, workspace_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- creation -----------------------------------------------------------

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        institution_name: str,
        full_name: str,
        department: str,
        campus: str,
        orcid_id: str | None,
    ) -> dict:
        """Create the workspace, its empty data files, and the owner's profile.

        Returns the created account row (including the new workspace id).
        """
        workspace_id = _slug(institution_name)
        now = datetime.now(UTC).isoformat(timespec="seconds")

        # The owner becomes the workspace's first researcher.
        researcher = {
            "researcher_id": 1,
            "full_name": full_name,
            "designation": "",
            "academic_rank": "",
            "department": department,
            "campus": campus,
            "institution": institution_name,
            "email": email.lower(),
            "orcid_id": orcid_id or None,
            "photo_url": None,
            "expertise": "",
            "publication_count": 0,
            "citation_count": 0,
            "topics": [],
            "research_areas": [],
            "profile_bio": "",
            "education": "",
            "source": "self-service",
        }

        workspace_dir(workspace_id).mkdir(parents=True, exist_ok=True)
        save("researchers", [researcher], workspace_id)
        for empty in ("publications", "projects", "topics"):
            save(empty, [], workspace_id)

        with self._connect() as con:
            con.execute(
                "INSERT INTO workspaces (workspace_id, institution_name, created_at)"
                " VALUES (?, ?, ?)",
                (workspace_id, institution_name, now),
            )
            con.execute(
                "INSERT INTO workspace_accounts (email, password_hash, workspace_id,"
                " researcher_id, full_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (email.lower(), password_hash, workspace_id, 1, full_name, now),
            )
        return {
            "email": email.lower(),
            "workspace_id": workspace_id,
            "researcher_id": 1,
            "full_name": full_name,
            "institution_name": institution_name,
        }


def is_demo(workspace_id: str) -> bool:
    return workspace_id == DEFAULT_WORKSPACE
