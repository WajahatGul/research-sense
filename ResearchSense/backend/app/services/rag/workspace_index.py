"""Builds the assistant's semantic index for one institution's workspace.

The demo corpus is indexed offline by ``scripts.build_index`` (it also chunks
the downloaded paper PDFs, which takes minutes). A signed-up institution holds
only its own profile, publications and research areas, so its index is small
enough to rebuild in place whenever that data changes — which is what makes the
assistant answer about the institution's own records instead of the demo's.

Rebuilds run as a background task after a write, so the request that saved the
data does not wait for the embedding model to load.
"""

from __future__ import annotations

import json
import logging

import numpy as np

from app.core.tenancy import institution_name
from app.repositories import loader
from app.services.rag.retriever import EMBED_MODEL, MODEL_CACHE, Retriever, index_dir

log = logging.getLogger(__name__)


def _rows(name: str, workspace: str) -> list[dict]:
    """Read a workspace file directly (not through the request-scoped cache)."""
    return loader._load(name, workspace)  # noqa: SLF001 - same package boundary


def _researcher_chunks(researchers: list[dict], owner: str) -> list[dict]:
    at = f"{owner}, " if owner else "the "
    out = []
    for r in researchers:
        parts = [
            f"{r['full_name']} is a {r.get('designation') or 'researcher'} in the "
            f"Department of {r.get('department') or 'their institution'} at "
            f"{at}{r.get('campus') or 'main'} campus."
        ]
        areas = r.get("research_areas") or [
            t["topic_name"] for t in (r.get("topics") or [])
        ]
        if areas:
            parts.append(f"Research areas: {', '.join(areas)}.")
        if r.get("education"):
            parts.append(f"Education: {r['education']}.")
        if r.get("profile_bio"):
            parts.append(r["profile_bio"])
        if r.get("email"):
            parts.append(f"Email: {r['email']}.")
        if r.get("publication_count"):
            parts.append(
                f"{r['full_name']} has {r['publication_count']} indexed "
                f"publications with {r.get('citation_count', 0)} total citations."
            )
        out.append(
            {
                "text": " ".join(parts),
                "kind": "researcher",
                "ref_id": r["researcher_id"],
                "label": f"{r['full_name']} — {r.get('designation') or 'Researcher'}",
            }
        )
    return out


def _publication_chunks(publications: list[dict]) -> list[dict]:
    out = []
    for p in publications:
        authors = ", ".join(a["full_name"] for a in p.get("authors", []))
        parts = [f'"{p["title"]}"']
        if authors:
            parts.append(f"was written by {authors}")
        if p.get("publication_year"):
            parts.append(f"and published in {p['publication_year']}")
        if p.get("journal_name"):
            parts.append(f"in {p['journal_name']}")
        text = " ".join(parts) + "."
        if p.get("abstract"):
            text += f" Abstract: {p['abstract']}"
        if p.get("doi"):
            text += f" DOI: {p['doi']}."
        out.append(
            {
                "text": text,
                "kind": "publication",
                "ref_id": p.get("publication_id"),
                "label": f"Publication: {p['title'][:70]}",
            }
        )
    return out


def _topic_chunks(topics: list[dict], researchers: list[dict]) -> list[dict]:
    out = []
    for t in topics:
        working = [
            r["full_name"]
            for r in researchers
            if t["topic_name"] in (r.get("research_areas") or [])
        ]
        text = f"{t['topic_name']} is a research area in this workspace."
        if working:
            text += f" Researchers working on it: {', '.join(working)}."
        if t.get("publication_count"):
            text += f" It covers {t['publication_count']} indexed publications."
        out.append(
            {
                "text": text,
                "kind": "topic",
                "ref_id": t.get("topic_id"),
                "label": f"Research area: {t['topic_name']}",
            }
        )
    return out


def chunks_for(workspace: str) -> list[dict]:
    """Every fact card the workspace's current data supports."""
    researchers = _rows("researchers", workspace)
    publications = _rows("publications", workspace)
    topics = _rows("topics", workspace)
    owner = institution_name(workspace)
    return (
        _researcher_chunks(researchers, owner)
        + _publication_chunks(publications)
        + _topic_chunks(topics, researchers)
    )


def rebuild(workspace: str) -> int:
    """Re-embed the workspace's records and replace its index. Returns chunks.

    Refuses the demo workspace: that index is built offline and also carries
    full-text paper chunks, which this structured build would throw away.
    """
    if workspace == loader.DEFAULT_WORKSPACE:
        raise ValueError("the demo index is built by 'python -m scripts.build_index'")

    chunks = chunks_for(workspace)
    if not chunks:
        return 0

    from fastembed import TextEmbedding  # deferred: slow import

    model = TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))
    vectors = np.array(list(model.embed([c["text"] for c in chunks])), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    directory = index_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8"
    )
    np.savez_compressed(directory / "rag_index.npz", vectors=vectors)

    Retriever.reset(workspace)  # next question loads the new index
    return len(chunks)


def rebuild_quietly(workspace: str) -> None:
    """Background-task wrapper: a failed re-index must never break a save.

    The structured fast paths keep answering from the saved JSON either way, so
    the worst case is that open-ended questions stay unavailable until the next
    write succeeds.
    """
    try:
        rebuild(workspace)
    except Exception:  # noqa: BLE001 - best-effort background work
        log.exception("workspace index rebuild failed for %s", workspace)
