import json

import numpy as np
import pytest

import app.repositories.accounts as accounts_mod
import app.services.staging as staging
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "test.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


def test_submission_lifecycle(store):
    sid = store.create_submission("publication", 7, "My Paper", '{"title":"My Paper"}')
    pending = store.pending_submissions()
    assert [p["id"] for p in pending] == [sid]
    store.set_submission_status(sid, "approved")
    assert store.pending_submissions() == []
    sub = store.get_submission(sid)
    assert sub["status"] == "approved" and sub["reviewed_at"] is not None


def test_reject_records_note(store):
    sid = store.create_submission("upload", 3, "T", "{}")
    store.set_submission_status(sid, "rejected", note="not a research paper")
    assert store.get_submission(sid)["note"] == "not a research paper"


def test_submissions_for_researcher(store):
    store.create_submission("upload", 3, "A", "{}")
    store.create_submission("upload", 4, "B", "{}")
    mine = store.submissions_for(3)
    assert [m["title"] for m in mine] == ["A"]


def test_stage_merge_roundtrip(tmp_path, monkeypatch):
    # Fake embedder: deterministic 4-dim vectors, no model download in tests.
    class FakeModel:
        def __init__(self, *a, **k): ...
        def embed(self, texts):
            return [np.ones(4, dtype=np.float32) * (i + 1) for i, _ in enumerate(texts)]

    monkeypatch.setattr(staging, "_embedder", lambda: FakeModel())
    monkeypatch.setattr(staging, "STAGED_DIR", tmp_path / "staged")
    monkeypatch.setattr(staging, "INDEX_DIR", tmp_path)
    (tmp_path / "rag_chunks.json").write_text("[]", "utf-8")
    np.savez_compressed(
        tmp_path / "rag_index.npz", vectors=np.zeros((0, 4), dtype=np.float32)
    )
    monkeypatch.setattr(staging, "_reset_retriever", lambda: None)

    n = staging.stage_chunks(
        5, [{"text": "hello world chunk", "kind": "paper", "ref_id": 1, "label": "L"}]
    )
    assert n == 1
    assert (tmp_path / "staged" / "sub-5.json").exists()

    merged = staging.merge_staged(5)
    assert merged == 1
    chunks = json.loads((tmp_path / "rag_chunks.json").read_text("utf-8"))
    assert len(chunks) == 1
    assert not (tmp_path / "staged" / "sub-5.json").exists()


def test_discard_removes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(staging, "STAGED_DIR", tmp_path / "staged")
    (tmp_path / "staged").mkdir()
    (tmp_path / "staged" / "sub-9.json").write_text("[]", "utf-8")
    (tmp_path / "staged" / "sub-9.npz").write_bytes(b"x")
    staging.discard_staged(9)
    assert not list((tmp_path / "staged").iterdir())


# --- FINDING 2: uploads must be linked to their submission, and a full
# index rebuild must only ever pick up approved (or legacy pre-approval)
# uploads — never pending or rejected ones. ---


def test_approved_uploads_excludes_pending_and_rejected(store):
    # Legacy row: no linked submission at all (pre-approval-era data) —
    # treated as already approved so existing installs keep working.
    store.record_upload(1, "Legacy Paper", "legacy.pdf")

    sid_pending = store.create_submission("upload", 2, "Pending Paper", "{}")
    store.record_upload(2, "Pending Paper", "pending.pdf", submission_id=sid_pending)

    sid_approved = store.create_submission("upload", 3, "Approved Paper", "{}")
    store.record_upload(3, "Approved Paper", "approved.pdf", submission_id=sid_approved)
    store.set_submission_status(sid_approved, "approved")

    sid_rejected = store.create_submission("upload", 4, "Rejected Paper", "{}")
    store.record_upload(4, "Rejected Paper", "rejected.pdf", submission_id=sid_rejected)
    store.set_submission_status(sid_rejected, "rejected")

    filenames = {row["filename"] for row in store.approved_uploads()}
    assert filenames == {"legacy.pdf", "approved.pdf"}


def test_delete_upload_for_submission_removes_row(store):
    sid = store.create_submission("upload", 5, "T", "{}")
    store.record_upload(5, "T", "t.pdf", submission_id=sid)
    store.set_submission_status(sid, "approved")
    assert {r["filename"] for r in store.approved_uploads()} == {"t.pdf"}

    store.delete_upload_for_submission(sid)
    assert store.approved_uploads() == []


def test_migration_adds_submission_id_column_to_existing_db(tmp_path, monkeypatch):
    """A database created before this change has an `uploads` table with no
    `submission_id` column. `CREATE TABLE IF NOT EXISTS` won't alter it, so
    AccountStore must migrate it on startup."""
    import sqlite3

    db_path = tmp_path / "pre_existing.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE uploads (id INTEGER PRIMARY KEY, researcher_id INTEGER,"
        " title TEXT, filename TEXT, uploaded_at TEXT)"
    )
    con.execute(
        "INSERT INTO uploads (researcher_id, title, filename, uploaded_at)"
        " VALUES (1, 'Old Paper', 'old.pdf', '2020-01-01')"
    )
    con.commit()
    con.close()

    monkeypatch.setattr(accounts_mod, "DB_PATH", db_path)
    AccountStore._instance = None
    migrated_store = AccountStore.instance()

    # Pre-existing rows survive the migration with submission_id NULL, so
    # they are treated as legacy/approved.
    assert {r["filename"] for r in migrated_store.approved_uploads()} == {"old.pdf"}
    AccountStore._instance = None
