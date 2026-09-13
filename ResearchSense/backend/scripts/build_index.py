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
import os
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

# Institution the index is branded for; empty for the neutral product-only look.
INSTITUTION = os.getenv("RS_INSTITUTION_NAME", "").strip()
# "... at Meridian University, Karachi campus" vs "... at the Karachi campus".
_AT_INST = f"{INSTITUTION}, " if INSTITUTION else "the "


def load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Fact cards from structured data
# ---------------------------------------------------------------------------
def _opening_sentence(r: dict) -> str:
    """How the profile introduces itself.

    A profile built from the publication record alone has no designation,
    department or campus, and slotting empty strings into the directory
    sentence produced "X is a  in the Department of  at the  campus." — text
    that reads badly in an answer and carries nothing to match a question
    against. Those profiles get a sentence about what they actually are.
    """
    name = r["full_name"]
    designation = (r.get("designation") or "").strip()
    department = (r.get("department") or "").strip()
    campus = (r.get("campus") or "").strip()

    if designation and department and campus:
        return (
            f"{name} is a {designation} in the Department of "
            f"{department} at {_AT_INST}{campus} campus."
        )

    # These profiles have nothing but a name and a publication record, so the
    # affiliation on the record is the one piece of context worth stating. It
    # comes from the data, keeping the build institution-agnostic.
    affiliation = (r.get("institution") or INSTITUTION).strip()
    where = f" at {affiliation}" if affiliation else ""
    if department:
        return f"{name} is a researcher in the Department of {department}{where}."
    return f"{name} is a researcher who has published{where}."


def researcher_chunks(researchers: list[dict]) -> list[dict]:
    out = []
    for r in researchers:
        parts = [_opening_sentence(r)]
        # Structured research areas (topic names) alongside the scraped
        # free-text expertise, so "who works on X" retrieves reliably.
        if r.get("topics"):
            areas = ", ".join(t["topic_name"] for t in r["topics"])
            parts.append(f"Research areas: {areas}.")
        if r.get("expertise"):
            parts.append(f"Expertise: {r['expertise']}.")
        # Derived research areas (hybrid: publication topics, falling back to
        # directory expertise) are distinct from the structured `topics` list
        # above, so surface them too when present and different.
        if r.get("research_areas"):
            parts.append(f"Derived research areas: {', '.join(r['research_areas'])}.")
        if r.get("education"):
            parts.append(f"Education: {r['education']}.")
        if r.get("email"):
            parts.append(f"Email: {r['email']}.")
        if r.get("publication_count"):
            parts.append(
                f"{r['full_name']} has {r['publication_count']} indexed "
                f"publications with {r['citation_count']} total citations."
            )
        intl = r.get("international_collaborations") or []
        if intl:
            partners = "; ".join(
                f"{i['institution']} ({i['country']})" for i in intl[:5]
            )
            parts.append(f"International collaborations: {partners}.")
        out.append(
            {
                "text": " ".join(parts),
                "kind": "researcher",
                "ref_id": r["researcher_id"],
                # Publication-only profiles have no designation; the bare
                # name reads better than a dangling "Name — " in a citation.
                "label": (
                    f"{r['full_name']} — {r['designation']}"
                    if (r.get("designation") or "").strip()
                    else r["full_name"]
                ),
            }
        )
    return out


def collaboration_chunks(
    researchers: list[dict], publications: list[dict]
) -> list[dict]:
    """One chunk per researcher naming who they have co-authored with, so the
    assistant can answer "who has X collaborated with" and "did X and Y work
    together" from retrieval (the fast path handles specific pairs precisely)."""
    from collections import Counter

    names = {r["researcher_id"]: r["full_name"] for r in researchers}
    coauth: dict[int, Counter] = {r["researcher_id"]: Counter() for r in researchers}
    for p in publications:
        ids = list(
            {
                a["researcher_id"]
                for a in p.get("authors", [])
                if a.get("researcher_id") in names
            }
        )
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
            for o, c in counter.most_common(12)
        )
        out.append(
            {
                "text": (
                    f"{names[rid]} has co-authored research papers with the "
                    f"following researchers: {listing}."
                ),
                "kind": "researcher",
                "ref_id": rid,
                "label": f"{names[rid]} — collaborators",
            }
        )
    return out


def publication_chunks(publications: list[dict]) -> list[dict]:
    out = []
    for p in publications:
        authors = ", ".join(a["full_name"] for a in p["authors"][:8])
        text = (
            f'Publication: "{p["title"]}" ({p["publication_year"]}), '
            f"{p['publication_type']} in {p['journal_name']}. "
            f"Authors: {authors}. Citations: {p['citation_count']}. "
            f"Campus: {p['campus']}."
        )
        if p.get("doi"):
            text += f" DOI: {p['doi']}."
        out.append(
            {
                "text": text,
                "kind": "publication",
                "ref_id": p["publication_id"],
                "label": f"{p['title'][:70]} ({p['publication_year']})",
            }
        )
    return out


def project_chunks(projects: list[dict]) -> list[dict]:
    out = []
    for p in projects:
        text = (
            f"Research project (illustrative example, not a confirmed grant): "
            f'"{p["project_title"]}". '
            f"Principal investigator: {p['principal_investigator_name']} "
            f"({p['campus']})."
        )
        out.append(
            {
                "text": text,
                "kind": "project",
                "ref_id": p["project_id"],
                "label": p["project_title"],
            }
        )
    return out


def topic_chunks(topics: list[dict]) -> list[dict]:
    out = []
    for t in topics:
        out.append(
            {
                "text": (
                    f"Research area {t['topic_name']} has "
                    f"{t['researcher_count']} researchers and "
                    f"{t['publication_count']} publications."
                ),
                "kind": "topic",
                "ref_id": t["topic_id"],
                "label": t["topic_name"],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Full-text chunks from downloaded papers
# ---------------------------------------------------------------------------
def _split(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_CHARS])
        start += CHUNK_CHARS - CHUNK_OVERLAP
    return [c.strip() for c in chunks if len(c.strip()) > 120]


def chunk_pdf(
    path: Path, title: str, year, author_name: str, researcher_id: int | None
) -> list[dict]:
    """Chunk one PDF into attributed index entries (shared with live uploads)."""
    reader = PdfReader(path)
    raw = " ".join((page.extract_text() or "") for page in reader.pages)
    text = re.sub(r"\s+", " ", raw).strip()
    header = f'From the paper "{title}" ({year}) by {author_name}: '
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
        author = paper.get("author_name") or names.get(rid, "a university researcher")
        try:
            out.extend(
                chunk_pdf(
                    PAPERS_DIR / paper["filename"],
                    paper["title"],
                    paper["year"],
                    author,
                    rid,
                )
            )
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
        header = f'From the paper "{title}" ({year}) in the research library: '
        out.extend(
            {
                "text": header + piece,
                "kind": "paper",
                "ref_id": None,
                "label": f"Library: {title[:60]} ({year})",
            }
            for piece in _split(text)
        )
    return out


# Embedding every chunk in one call materialises the whole batch inside the
# ONNX runtime; at ~21k chunks that peaked near 1.6 GB. Feeding it in slices
# keeps the working set flat, which matters because the same code path runs
# inside the deployed app during a refresh.
EMBED_BATCH = 512


def embed_all(texts: list[str], model: TextEmbedding) -> np.ndarray:
    """Embed in slices and return one normalized float32 matrix."""
    out = np.empty((len(texts), 384), dtype=np.float32)
    done = 0
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        vecs = np.array(list(model.embed(batch)), dtype=np.float32)
        out[start : start + len(batch)] = vecs
        done += len(batch)
        print(f"  embedded {done}/{len(texts)} chunks", flush=True)
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    return out


def fact_card_chunks() -> list[dict]:
    """All chunks derived from the structured JSON data (no PDFs)."""
    researchers = load("researchers")
    publications = load("publications")
    return (
        researcher_chunks(researchers)
        + collaboration_chunks(researchers, publications)
        + publication_chunks(publications)
        + project_chunks(load("projects"))
        + topic_chunks(load("topics"))
    )


def rebuild_preserving_fulltext() -> None:
    """Refresh the fact cards while KEEPING every full-text chunk.

    Data refreshes change the structured JSON, not the PDFs — so the paper
    chunks (downloaded papers, faculty uploads, the library) and their
    embeddings are carried over from the existing index unchanged. This is
    what the weekly/admin refresh runs: a from-scratch main() would silently
    drop faculty uploads (never re-included) and, on machines where the
    gitignored PDFs are absent, all downloaded-paper full text as well.
    """
    print("Refreshing index fact cards (preserving full-text chunks)...")
    existing_chunks = json.loads((DATA_DIR / "rag_chunks.json").read_text("utf-8"))
    existing_vectors = np.load(DATA_DIR / "rag_index.npz")["vectors"]
    keep = [i for i, c in enumerate(existing_chunks) if c["kind"] == "paper"]
    kept_chunks = [existing_chunks[i] for i in keep]
    kept_vectors = existing_vectors[keep]

    fresh = fact_card_chunks()
    model = TextEmbedding(EMBED_MODEL)
    fresh_vectors = embed_all([c["text"] for c in fresh], model)

    chunks = fresh + kept_chunks
    vectors = np.vstack([fresh_vectors, kept_vectors])
    (DATA_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8"
    )
    np.savez_compressed(DATA_DIR / "rag_index.npz", vectors=vectors)
    print(
        f"  {len(fresh)} fact cards rebuilt, {len(kept_chunks)} full-text "
        f"chunks preserved (matrix {vectors.shape[0]}x{vectors.shape[1]})"
    )


def upload_chunks() -> list[dict]:
    """Faculty-uploaded papers (papers/uploads + the SQLite uploads table),
    re-chunked for full builds so uploads survive a from-scratch rebuild.

    Only APPROVED uploads (plus pre-approval-era rows with no linked
    submission) are included — a pending or rejected upload must never be
    indexed by a from-scratch rebuild, since that would bypass the admin
    review gate. Selection lives in AccountStore.approved_uploads() so it is
    unit-testable without going through this script."""
    db = DATA_DIR / "researchsense.db"
    uploads_dir = PAPERS_DIR / "uploads"
    if not db.exists() or not uploads_dir.exists():
        return []
    from app.repositories.accounts import AccountStore

    names = {r["researcher_id"]: r["full_name"] for r in load("researchers")}
    rows = AccountStore.instance().approved_uploads()
    out = []
    for row in rows:
        path = uploads_dir / row["filename"]
        if not path.exists():
            continue
        try:
            reader = PdfReader(path)
            raw = " ".join((page.extract_text() or "") for page in reader.pages)
            text = re.sub(r"\s+", " ", raw).strip()
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"  ! could not read upload {row['filename']}: {exc}")
            continue
        author = names.get(row["researcher_id"], "a university researcher")
        header = f'From the paper "{row["title"]}" by {author}: '
        out.extend(
            {
                "text": header + piece,
                "kind": "paper",
                "ref_id": row["researcher_id"],
                "label": f"Paper: {row['title'][:70]} (uploaded)",
            }
            for piece in _split(text)
        )
    return out


def main() -> None:
    print("Building RAG index...")
    researchers = load("researchers")
    chunks = fact_card_chunks()
    papers = paper_chunks(researchers) + upload_chunks()
    chunks += papers
    library = library_paper_chunks()
    chunks += library
    print(
        f"  {len(chunks)} chunks ({len(papers)} from paper full text, "
        f"{len(library)} from the library)"
    )

    model = TextEmbedding(EMBED_MODEL)
    # Normalized inside, so cosine similarity is a plain dot product at query time.
    vectors = embed_all([c["text"] for c in chunks], model)

    (DATA_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8"
    )
    np.savez_compressed(DATA_DIR / "rag_index.npz", vectors=vectors)
    print(
        f"  wrote rag_chunks.json + rag_index.npz "
        f"(matrix {vectors.shape[0]}x{vectors.shape[1]})"
    )
    print("Done.")


if __name__ == "__main__":
    main()
