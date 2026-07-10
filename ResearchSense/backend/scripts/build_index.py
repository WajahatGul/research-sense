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
        if r.get("expertise"):
            parts.append(f"Research areas and expertise: {r['expertise']}.")
        if r.get("education"):
            parts.append(f"Education: {r['education']}.")
        if r.get("email"):
            parts.append(f"Email: {r['email']}.")
        if r.get("publication_count"):
            parts.append(
                f"Has {r['publication_count']} indexed publications with "
                f"{r['citation_count']} total citations.")
        out.append({
            "text": " ".join(parts),
            "kind": "researcher",
            "ref_id": r["researcher_id"],
            "label": f"{r['full_name']} — {r['designation']}",
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


def _author_researcher_id(researchers: list[dict], name: str) -> int | None:
    """Match the papers' author to a researcher so paper sources can link
    to their profile in the UI."""
    key = re.sub(r"[^a-z]", "", name.lower())
    for r in researchers:
        if re.sub(r"[^a-z]", "", r["full_name"].lower()).endswith(key):
            return r["researcher_id"]
    return None


def paper_chunks(researchers: list[dict]) -> list[dict]:
    manifest_path = PAPERS_DIR / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text("utf-8"))
    author_id = _author_researcher_id(researchers, "Arif ur Rahman")
    out = []
    for paper in manifest:
        path = PAPERS_DIR / paper["filename"]
        try:
            reader = PdfReader(path)
            raw = " ".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # noqa: BLE001 - skip unreadable files
            print(f"  ! could not read {paper['filename']}: {exc}")
            continue
        text = re.sub(r"\s+", " ", raw).strip()
        header = f"From the paper \"{paper['title']}\" ({paper['year']}) by Arif Ur Rahman: "
        for piece in _split(text):
            out.append({
                "text": header + piece,
                "kind": "paper",
                "ref_id": author_id,  # links the source chip to the author
                "label": f"Paper: {paper['title'][:70]} ({paper['year']})",
            })
    return out


def main() -> None:
    print("Building RAG index...")
    researchers = load("researchers")
    chunks = (
        researcher_chunks(researchers)
        + publication_chunks(load("publications"))
        + project_chunks(load("projects"))
        + topic_chunks(load("topics"))
    )
    papers = paper_chunks(researchers)
    chunks += papers
    print(f"  {len(chunks)} chunks ({len(papers)} from paper full text)")

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
