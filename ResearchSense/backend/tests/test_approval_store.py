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
