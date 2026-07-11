"""Paper library: study ANY paper with the assistant, without attribution.

"Add a publication" attributes a paper to the submitting researcher and is
gated on authorship. This module is the complementary flow: index a paper
into the assistant's library purely for reading and question-answering — no
profile attribution, no authorship requirement.

By DOI: metadata comes from the registries (same resolver as submissions) and
the open-access PDF is located via OpenAlex, then Semantic Scholar — the same
sources the bulk paper pipeline uses. No open-access copy -> the caller is
told to upload the PDF instead. Library entries are recorded in
papers/library/library_manifest.json so index rebuilds re-include them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.services.rag import indexer
from app.services.submission_service import (SubmissionError,
                                             fetch_doi_metadata)

BACKEND = Path(__file__).resolve().parents[2]
LIBRARY_DIR = BACKEND / "papers" / "library"
MANIFEST = LIBRARY_DIR / "library_manifest.json"

OPENALEX_API = "https://api.openalex.org/works"
S2_API = "https://api.semanticscholar.org/graph/v1/paper"
HEADERS = {"User-Agent": "Mozilla/5.0 ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
MAX_BYTES = 30 * 1024 * 1024  # 30 MB


class LibraryError(Exception):
    """User-facing library failure (no OA PDF, duplicate, bad file...)."""


def _manifest() -> list[dict]:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text("utf-8"))
    return []


def _save_manifest(entries: list[dict]) -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                        "utf-8")


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _already_in_library(doi: str | None, title: str) -> dict | None:
    t = _norm_title(title)
    for e in _manifest():
        if doi and e.get("doi") and e["doi"].lower() == doi.lower():
            return e
        if _norm_title(e.get("title", "")) == t:
            return e
    return None


def _safe_filename(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"lib-{slug}.pdf"


def library_chunks(text: str, title: str, year) -> list[dict]:
    """Neutral (unattributed) chunks for a library paper. ref_id None keeps
    the chat source chip from pointing at any researcher."""
    header = f"From the paper \"{title}\" ({year}) in the research library: "
    return [
        {
            "text": header + piece,
            "kind": "paper",
            "ref_id": None,
            "label": f"Library: {title[:60]} ({year})",
        }
        for piece in indexer._split(text)
    ]


# ---------------------------------------------------------------------------
# Open-access PDF discovery (OpenAlex locations -> Semantic Scholar)
# ---------------------------------------------------------------------------

def _openalex_pdf_urls(doi: str, client: httpx.Client) -> list[str]:
    try:
        resp = client.get(f"{OPENALEX_API}/https://doi.org/{doi}")
        if resp.status_code != 200:
            return []
        work = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    urls: list[str] = []
    for loc in ([work.get("best_oa_location"), work.get("primary_location")]
                + (work.get("locations") or [])):
        pdf = (loc or {}).get("pdf_url")
        if pdf and pdf not in urls:
            urls.append(pdf)
    return urls


def _semantic_scholar_pdf(doi: str, client: httpx.Client) -> str | None:
    try:
        resp = client.get(f"{S2_API}/DOI:{doi}",
                          params={"fields": "openAccessPdf"})
        if resp.status_code == 200:
            return (resp.json().get("openAccessPdf") or {}).get("url")
    except (httpx.HTTPError, ValueError):
        pass
    return None


def _download_pdf(doi: str) -> bytes:
    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        candidates = _openalex_pdf_urls(doi, client)
        s2 = _semantic_scholar_pdf(doi, client)
        if s2 and s2 not in candidates:
            candidates.append(s2)
        for url in candidates:
            try:
                resp = client.get(url)
            except httpx.HTTPError:
                continue
            data = resp.content
            if (resp.status_code == 200 and data[:5] == b"%PDF-"
                    and 10_000 < len(data) <= MAX_BYTES):
                return data
    raise LibraryError(
        "No open-access PDF could be found for this DOI. If you have the "
        "file, upload the PDF instead.")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def _index_and_record(pdf_path: Path, doi: str | None, title: str,
                      year, added_by: int | None) -> dict:
    try:
        text = indexer.extract_pdf_text(pdf_path)
    except ValueError as exc:
        pdf_path.unlink(missing_ok=True)
        raise LibraryError(str(exc))
    chunks = library_chunks(text, title, year)
    if not chunks:
        pdf_path.unlink(missing_ok=True)
        raise LibraryError("The PDF is too short to index")
    added = indexer.append_chunks(chunks)

    entries = _manifest()
    entries.append({
        "doi": doi,
        "title": title,
        "year": year,
        "filename": pdf_path.name,
        "chunks": added,
        "added_by": added_by,
        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    _save_manifest(entries)
    return {"title": title, "chunks_added": added}


def study_doi(doi: str, added_by: int | None = None) -> dict:
    """Fetch an open-access paper by DOI and index it into the library."""
    try:
        meta = fetch_doi_metadata(doi)
    except SubmissionError as exc:
        raise LibraryError(str(exc))
    if _already_in_library(meta["doi"], meta["title"]):
        raise LibraryError("This paper is already in the library — you can "
                           "ask the assistant about it right away.")
    data = _download_pdf(meta["doi"])
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    path = LIBRARY_DIR / _safe_filename(meta["title"])
    path.write_bytes(data)
    return _index_and_record(path, meta["doi"], meta["title"],
                             meta["publication_year"], added_by)


def study_upload(data: bytes, title: str, added_by: int | None = None) -> dict:
    """Index an uploaded PDF into the library (no attribution)."""
    title = title.strip()
    if _already_in_library(None, title):
        raise LibraryError("A paper with this title is already in the library.")
    if data[:5] != b"%PDF-":
        raise LibraryError("The file is not a PDF")
    if len(data) > MAX_BYTES:
        raise LibraryError("PDF larger than 30 MB")
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    path = LIBRARY_DIR / _safe_filename(title)
    path.write_bytes(data)
    return _index_and_record(path, None, title, "n.d.", added_by)


def list_library() -> list[dict]:
    """All library entries, newest first."""
    return sorted(_manifest(), key=lambda e: e.get("added_at", ""),
                  reverse=True)


def remove_paper(filename: str, requester_id: int | None,
                 is_admin: bool) -> dict:
    """Remove one library paper: its index chunks, manifest entry, and PDF.

    Allowed for the researcher who added it and for admins.
    """
    entries = _manifest()
    entry = next((e for e in entries if e["filename"] == filename), None)
    if entry is None:
        raise LibraryError("This paper is not in the library.")
    if not is_admin and entry.get("added_by") != requester_id:
        raise LibraryError(
            "Only the person who added this paper (or an admin) can remove it.")

    # Drop the paper's chunks from the live index. The label is deterministic
    # (same formula as library_chunks), so it identifies exactly this paper.
    import json as _json

    import numpy as np

    from app.services.rag.retriever import DATA_DIR as INDEX_DIR
    from app.services.rag.retriever import Retriever

    label = f"Library: {entry['title'][:60]} ({entry.get('year', 'n.d.')})"
    chunks = _json.loads((INDEX_DIR / "rag_chunks.json").read_text("utf-8"))
    vectors = np.load(INDEX_DIR / "rag_index.npz")["vectors"]
    keep = [i for i, c in enumerate(chunks) if c.get("label") != label]
    removed = len(chunks) - len(keep)
    if removed:
        (INDEX_DIR / "rag_chunks.json").write_text(
            _json.dumps([chunks[i] for i in keep], ensure_ascii=False), "utf-8")
        np.savez_compressed(INDEX_DIR / "rag_index.npz", vectors=vectors[keep])
        Retriever.reset()

    (LIBRARY_DIR / filename).unlink(missing_ok=True)
    _save_manifest([e for e in entries if e["filename"] != filename])
    return {"title": entry["title"], "chunks_removed": removed}
