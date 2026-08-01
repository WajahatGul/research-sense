"""Regression tests for staged-chunk merging on approval.

The live RAG index is built lazily at deploy and can be absent (ephemeral disk,
local dev). Approving a paper must never crash on a missing index — it should
initialise one from the staged chunks so the paper still becomes searchable.
"""

from __future__ import annotations

import json

import numpy as np

from app.services import staging


def _write_staged(sub_id: int, chunks: list[dict], vecs, staged_dir) -> None:
    staged_dir.mkdir(parents=True, exist_ok=True)
    (staged_dir / f"sub-{sub_id}.json").write_text(json.dumps(chunks), "utf-8")
    np.savez_compressed(
        staged_dir / f"sub-{sub_id}.npz", vectors=np.asarray(vecs, dtype=np.float32)
    )


def _isolate(tmp_path, monkeypatch):
    index_dir = tmp_path / "data"
    staged_dir = tmp_path / "staged"
    index_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(staging, "INDEX_DIR", index_dir)
    monkeypatch.setattr(staging, "STAGED_DIR", staged_dir)
    monkeypatch.setattr(staging, "_reset_retriever", lambda: None)
    return index_dir, staged_dir


def test_merge_staged_creates_index_when_absent(tmp_path, monkeypatch):
    index_dir, staged_dir = _isolate(tmp_path, monkeypatch)
    chunks = [{"text": "a paper", "kind": "publication", "ref_id": 1, "label": "X"}]
    _write_staged(5, chunks, [[0.1, 0.2, 0.3, 0.4]], staged_dir)

    # No live index yet -> must not raise, and must create a valid one.
    merged = staging.merge_staged(5)

    assert merged == 1
    assert (index_dir / "rag_chunks.json").exists()
    assert (index_dir / "rag_index.npz").exists()
    assert json.loads((index_dir / "rag_chunks.json").read_text("utf-8")) == chunks
    assert np.load(index_dir / "rag_index.npz")["vectors"].shape == (1, 4)


def test_merge_staged_appends_to_existing_index(tmp_path, monkeypatch):
    index_dir, staged_dir = _isolate(tmp_path, monkeypatch)
    (index_dir / "rag_chunks.json").write_text(
        json.dumps([{"text": "c0"}, {"text": "c1"}]), "utf-8"
    )
    np.savez_compressed(
        index_dir / "rag_index.npz", vectors=np.zeros((2, 4), dtype=np.float32)
    )
    _write_staged(6, [{"text": "c2"}], [[1, 0, 0, 0]], staged_dir)

    merged = staging.merge_staged(6)

    assert merged == 1
    assert len(json.loads((index_dir / "rag_chunks.json").read_text("utf-8"))) == 3
    assert np.load(index_dir / "rag_index.npz")["vectors"].shape == (3, 4)


def test_merge_staged_missing_stage_returns_zero(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert staging.merge_staged(999) == 0
