"""Incremental additions to the RAG index (used by faculty paper uploads).

Chunks and embeds one PDF, appends it to rag_chunks.json + rag_index.npz, and
resets the in-memory retriever so the chatbot can answer from the new paper
immediately. A full rebuild (scripts/build_index.py) remains the way to
regenerate everything from scratch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from pypdf import PdfReader

from app.services.rag.retriever import DATA_DIR, MODEL_CACHE, EMBED_MODEL, Retriever

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150


def _split(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_CHARS])
        start += CHUNK_CHARS - CHUNK_OVERLAP
    return [c.strip() for c in chunks if len(c.strip()) > 120]


def extract_pdf_text(pdf_path: Path) -> str:
    """Full text of a PDF. Raises ValueError when nothing is extractable, so
    callers can reject scanned/image-only files loudly."""
    reader = PdfReader(pdf_path)
    raw = " ".join((page.extract_text() or "") for page in reader.pages)
    text = re.sub(r"\s+", " ", raw).strip()
    if len(text) < 300:
        raise ValueError("The PDF contains no extractable text")
    return text


def append_chunks(new_chunks: list[dict]) -> int:
    """Embed chunk dicts ({text, kind, ref_id, label}) and append them to the
    live index; the retriever reloads on the next question."""
    if not new_chunks:
        raise ValueError("Nothing to index")

    from fastembed import TextEmbedding  # deferred: slow import

    model = TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))
    vectors = np.array(
        list(model.embed([c["text"] for c in new_chunks])), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    chunks = json.loads((DATA_DIR / "rag_chunks.json").read_text("utf-8"))
    existing = np.load(DATA_DIR / "rag_index.npz")["vectors"]

    chunks.extend(new_chunks)
    combined = np.vstack([existing, vectors])
    (DATA_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8")
    np.savez_compressed(DATA_DIR / "rag_index.npz", vectors=combined)

    Retriever.reset()  # next question loads the updated index
    return len(new_chunks)


def add_paper(pdf_path: Path, title: str, author_name: str,
              researcher_id: int) -> int:
    """Index one uploaded faculty paper (attributed). Returns chunks added."""
    text = extract_pdf_text(pdf_path)
    header = f"From the paper \"{title}\" by {author_name}: "
    new_chunks = [
        {
            "text": header + piece,
            "kind": "paper",
            "ref_id": researcher_id,
            "label": f"Paper: {title[:70]} (uploaded)",
        }
        for piece in _split(text)
    ]
    if not new_chunks:
        raise ValueError("The PDF is too short to index")
    return append_chunks(new_chunks)
