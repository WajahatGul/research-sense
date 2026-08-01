"""Staged RAG chunks for papers awaiting admin approval (SRS 7).

Embedding runs at submission time so approval is instant: merge_staged only
appends the precomputed vectors to the live index. Rejection discards the
staged files. Nothing here touches publications.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.rag.retriever import DATA_DIR as INDEX_DIR
from app.services.rag.retriever import EMBED_MODEL, MODEL_CACHE, Retriever

STAGED_DIR = Path(__file__).resolve().parents[1] / "data" / "staged"


def _embedder():
    from fastembed import TextEmbedding  # deferred: slow import

    return TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))


def _reset_retriever() -> None:
    Retriever.reset()


def _paths(sub_id: int) -> tuple[Path, Path]:
    return STAGED_DIR / f"sub-{sub_id}.json", STAGED_DIR / f"sub-{sub_id}.npz"


def stage_chunks(sub_id: int, chunks: list[dict]) -> int:
    """Embed and store chunks for one pending submission. Returns count."""
    if not chunks:
        raise ValueError("Nothing to stage")
    vectors = np.array(
        list(_embedder().embed([c["text"] for c in chunks])), dtype=np.float32
    )
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    cpath, vpath = _paths(sub_id)
    cpath.write_text(json.dumps(chunks, ensure_ascii=False), "utf-8")
    np.savez_compressed(vpath, vectors=vectors)
    return len(chunks)


def merge_staged(sub_id: int) -> int:
    """Append a submission's staged chunks+vectors to the live index."""
    cpath, vpath = _paths(sub_id)
    if not cpath.exists() or not vpath.exists():
        return 0
    new_chunks = json.loads(cpath.read_text("utf-8"))
    new_vecs = np.load(vpath)["vectors"]

    # The live index may be absent — it is built lazily at deploy, can be wiped
    # by an ephemeral disk on restart, or is simply not built yet in local dev.
    # Start from empty so approval still succeeds (and the paper becomes
    # searchable) instead of crashing on a missing file; a later full rebuild
    # restores the rest of the corpus.
    chunks_path = INDEX_DIR / "rag_chunks.json"
    index_path = INDEX_DIR / "rag_index.npz"
    if chunks_path.exists() and index_path.exists():
        chunks = json.loads(chunks_path.read_text("utf-8"))
        existing = np.load(index_path)["vectors"]
    else:
        chunks = []
        existing = np.zeros((0, new_vecs.shape[1]), dtype=np.float32)

    chunks.extend(new_chunks)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), "utf-8")
    base = (
        existing
        if existing.size
        else np.zeros((0, new_vecs.shape[1]), dtype=np.float32)
    )
    np.savez_compressed(index_path, vectors=np.vstack([base, new_vecs]))
    cpath.unlink()
    vpath.unlink()
    _reset_retriever()
    return len(new_chunks)


def discard_staged(sub_id: int) -> None:
    for p in _paths(sub_id):
        p.unlink(missing_ok=True)
