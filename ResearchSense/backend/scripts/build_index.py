"""Build the RAG vector index for the ResearchSense chatbot.

Corpus = fact cards from the structured JSON data (researchers, publications,
projects, topics) + full-text chunks from the downloaded papers. Every chunk
carries source metadata ({kind, ref_id, label}) so answers can cite the exact
record they came from.

Embeddings: all-MiniLM-L6-v2 via fastembed (local, CPU, free). Output:
  app/data/rag_chunks.json  — chunk texts + metadata
  app/data/rag_index.npz    — float32 matrix of normalized embeddings

Run (from backend/):  python -m scripts.build_index
Re-run whenever the seed data or the papers folder changes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from pypdf import PdfReader

BACKEND = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND / "app" / "data"
PAPERS_DIR = BACKEND / "papers"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150


def load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Fact cards from structured data
# ---------------------------------------------------------------------------
def researcher_chunks(researchers: list[dict]) -> list[dict]:
    out = []
    for r in researchers:
        parts = [
            f"{r['full_name']} is a {r['designation']} in the Department of "
            f"{r['department']} at Bahria University, {r['campus']} campus."
        ]
        # Structured research areas (topic names) alongside the scraped
        # free-text expertise, so "who works on X" retrieves reliably.
        if r.get("topics"):
            areas = ", ".join(t["topic_name"] for t in r["topics"])
            parts.append(f"Research areas: {areas}.")
        if r.get("expertise"):
            parts.append(f"Expertise: {r['expertise']}.")
        if r.get("education"):
            parts.append(f"Education: {r['education']}.")
        if r.get("email"):
            parts.append(f"Email: {r['email']}.")
        if r.get("publication_count"):
            parts.append(
                f"{r['full_name']} has {r['publication_count']} indexed "
                f"publications with {r['citation_count']} total citations.")
        out.append({
            "text": " ".join(parts),
            "kind": "researcher",
            "ref_id": r["researcher_id"],
            "label": f"{r['full_name']} — {r['designation']}",
        })
    return out


def collaboration_chunks(researchers: list[dict],
                         publications: list[dict]) -> list[dict]:
    """One chunk per researcher naming who they have co-authored with, so the
    assistant can answer "who has X collaborated with" and "did X and Y work
    together" from retrieval (the fast path handles specific pairs precisely)."""
    from collections import Counter

    names = {r["researcher_id"]: r["full_name"] for r in researchers}
    coauth: dict[int, Counter] = {r["researcher_id"]: Counter()
                                  for r in researchers}
    for p in publications:
        ids = list({a["researcher_id"] for a in p.get("authors", [])
                    if a.get("researcher_id") in names})
        for a in ids:
            for b in ids:
                if a != b:
                    coauth[a][b] += 1

    out = []
    for rid, counter in coauth.items():
        if not counter:
            continue
        listing = ", ".join(
            f"{names[o]} ({c} paper{'s' if c > 1 else ''})"
            for o, c in counter.most_common(12))
        out.append({
            "text": (f"{names[rid]} has co-authored research papers with the "
                     f"following Bahria University researchers: {listing}."),
            "kind": "researcher",
            "ref_id": rid,
            "label": f"{names[rid]} — collaborators",
        })
    return out


def publication_chunks(publications: list[dict]) -> list[dict]:
    out = []
    for p in publications:
        authors = ", ".join(a["full_name"] for a in p["authors"][:8])
        text = (
            f"Publication: \"{p['title']}\" ({p['publication_year']}), "
            f"{p['publication_type']} in {p['journal_name']}. "
            f"Authors: {authors}. Citations: {p['citation_count']}. "
            f"Campus: {p['campus']}."
        )
        if p.get("doi"):
            text += f" DOI: {p['doi']}."
        out.append({
            "text": text,
            "kind": "publication",
            "ref_id": p["publication_id"],
            "label": f"{p['title'][:70]} ({p['publication_year']})",
        })
    return out


def project_chunks(projects: list[dict]) -> list[dict]:
    out = []
    for p in projects:
        fund = p["funding"][0] if p.get("funding") else {}
        amount = f"{fund.get('amount', 0):,.0f} {fund.get('currency', 'PKR')}"
        text = (
            f"Research project (demonstration record, not a confirmed grant): "
            f"\"{p['project_title']}\", {p['status']}, "
            f"{p['start_date']} to {p.get('end_date') or 'ongoing'}. "
            f"Principal investigator: {p['principal_investigator_name']} "
            f"({p['campus']}). Funded by {fund.get('agency_name', 'n/a')}, "
            f"amount {amount}."
        )
        out.append({
            "text": text,
            "kind": "project",
            "ref_id": p["project_id"],
            "label": p["project_title"],
        })
    return out


def topic_chunks(topics: list[dict]) -> list[dict]:
    out = []
    for t in topics:
        out.append({
            "text": (f"Research area {t['topic_name']} at Bahria University has "
                     f"{t['researcher_count']} researchers and "
                     f"{t['publication_count']} publications."),
            "kind": "topic",
            "ref_id": t["topic_id"],
            "label": t["topic_name"],
        })
    return out


# ---------------------------------------------------------------------------
# Full-text chunks from downloaded papers
# ---------------------------------------------------------------------------
def _split(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_CHARS])
        start += CHUNK_CHARS - CHUNK_OVERLAP
    return [c.strip() for c in chunks if len(c.strip()) > 120]


def chunk_pdf(path: Path, title: str, year, author_name: str,
              researcher_id: int | None) -> list[dict]:
    """Chunk one PDF into attributed index entries (shared with live uploads)."""
    reader = PdfReader(path)
    raw = " ".join((page.extract_text() or "") for page in reader.pages)
    text = re.sub(r"\s+", " ", raw).strip()
    header = f"From the paper \"{title}\" ({year}) by {author_name}: "
    return [
        {
            "text": header + piece,
            "kind": "paper",
            "ref_id": researcher_id,  # links the source chip to the author
            "label": f"Paper: {title[:70]} ({year})",
        }
        for piece in _split(text)
    ]


def paper_chunks(researchers: list[dict]) -> list[dict]:
    manifest_path = PAPERS_DIR / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text("utf-8"))
    names = {r["researcher_id"]: r["full_name"] for r in researchers}
    out = []
    for paper in manifest:
        rid = paper.get("researcher_id")
        author = paper.get("author_name") or names.get(rid, "a Bahria researcher")
        try:
            out.extend(chunk_pdf(PAPERS_DIR / paper["filename"], paper["title"],
                                 paper["year"], author, rid))
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"  ! could not read {paper['filename']}: {exc}")
    return out


def library_paper_chunks() -> list[dict]:
    """Unattributed library papers ('study any paper'), recorded in
    papers/library/library_manifest.json — re-included on every rebuild."""
    manifest_path = PAPERS_DIR / "library" / "library_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text("utf-8"))
    out = []
    for paper in manifest:
        path = PAPERS_DIR / "library" / paper["filename"]
        try:
            reader = PdfReader(path)
            raw = " ".join((page.extract_text() or "") for page in reader.pages)
            text = re.sub(r"\s+", " ", raw).strip()
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"  ! could not read library {paper['filename']}: {exc}")
            continue
        title, year = paper["title"], paper.get("year", "n.d.")
        header = f"From the paper \"{title}\" ({year}) in the research library: "
        out.extend({
            "text": header + piece,
            "kind": "paper",
            "ref_id": None,
            "label": f"Library: {title[:60]} ({year})",
        } for piece in _split(text))
    return out


def main() -> None:
    print("Building RAG index...")
    researchers = load("researchers")
    publications = load("publications")
    chunks = (
        researcher_chunks(researchers)
        + collaboration_chunks(researchers, publications)
        + publication_chunks(publications)
        + project_chunks(load("projects"))
        + topic_chunks(load("topics"))
    )
    papers = paper_chunks(researchers)
    chunks += papers
    library = library_paper_chunks()
    chunks += library
    print(f"  {len(chunks)} chunks ({len(papers)} from paper full text, "
          f"{len(library)} from the library)")

    model = TextEmbedding(EMBED_MODEL)
    vectors = np.array(
        list(model.embed([c["text"] for c in chunks])), dtype=np.float32)
    # Normalize so cosine similarity is a plain dot product at query time.
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    (DATA_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8")
    np.savez_compressed(DATA_DIR / "rag_index.npz", vectors=vectors)
    print(f"  wrote rag_chunks.json + rag_index.npz "
          f"(matrix {vectors.shape[0]}x{vectors.shape[1]})")
    print("Done.")


if __name__ == "__main__":
    main()
