"""Faculty publication submission (proposal: publication ingestion pipeline).

Two entry methods, mirroring the FYP proposal:
  1. DOI-based — the researcher pastes a DOI, we retrieve metadata from the
     Crossref API, they verify it, and the record is stored.
  2. Manual — when no DOI exists, the researcher enters the details directly.

Submitted records are appended to publications.json (so they appear in the
dashboard, profile pages, and search immediately) AND to
submitted_publications.json — a durable store the weekly OpenAlex refresh
re-merges, so faculty submissions survive data refreshes. Each submission is
also embedded into the live RAG index so the chatbot can answer about it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from app.repositories import loader

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CROSSREF_API = "https://api.crossref.org/works"
DATACITE_API = "https://api.datacite.org/dois"
OPENALEX_API = "https://api.openalex.org/works"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}


class SubmissionError(Exception):
    """User-facing submission failure (bad DOI, duplicate, etc.)."""


def _norm_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi.strip("/ ")


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _name_key(name: str) -> str:
    """Roster-matching key, same scheme as scripts.fetch_publications."""
    name = re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s*", "", name.strip().lower())
    return re.sub(r"[^a-z]", "", name)


def _strip_jats(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


# ---------------------------------------------------------------------------
# DOI metadata retrieval: Crossref, DataCite fallback, OpenAlex concepts
# ---------------------------------------------------------------------------

def _fetch_crossref(doi: str) -> dict | None:
    """Crossref record for a DOI, or None when Crossref has no record."""
    try:
        resp = httpx.get(f"{CROSSREF_API}/{doi}", headers=HEADERS, timeout=30,
                         follow_redirects=True)
    except httpx.HTTPError as exc:
        raise SubmissionError(f"Could not reach Crossref: {exc}") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise SubmissionError(f"Crossref lookup failed (HTTP {resp.status_code}).")

    msg = resp.json().get("message", {})
    title = " ".join(msg.get("title") or []).strip()
    if not title:
        return None

    authors, author_orcids = [], []
    for a in msg.get("author", []) or []:
        name = " ".join(filter(None, [a.get("given"), a.get("family")])).strip()
        if name:
            authors.append(name)
        if a.get("ORCID"):
            author_orcids.append(a["ORCID"])

    date_parts = ((msg.get("published-print") or msg.get("published-online")
                   or msg.get("issued") or {}).get("date-parts") or [[None]])
    year = date_parts[0][0] or 0

    venue = " ".join(msg.get("container-title") or []).strip()
    pub_type = ("conference" if msg.get("type") == "proceedings-article"
                else "journal")

    return {
        "doi": doi,
        "title": title,
        "authors": authors,
        "author_orcids": author_orcids,
        "publication_year": int(year) if year else 0,
        "journal_name": venue or "Preprint or unindexed venue",
        "publication_type": pub_type,
        "citation_count": int(msg.get("is-referenced-by-count") or 0),
        "abstract": _strip_jats(msg.get("abstract") or "")[:700],
    }


def _fetch_datacite(doi: str) -> dict | None:
    """DataCite record fallback (datasets, preprints, Zenodo, etc.)."""
    try:
        resp = httpx.get(f"{DATACITE_API}/{doi}", headers=HEADERS, timeout=30,
                         follow_redirects=True)
    except httpx.HTTPError as exc:
        raise SubmissionError(f"Could not reach DataCite: {exc}") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise SubmissionError(f"DataCite lookup failed (HTTP {resp.status_code}).")

    attrs = (resp.json().get("data") or {}).get("attributes") or {}
    title = " ".join(t.get("title", "") for t in attrs.get("titles") or []).strip()
    if not title:
        return None

    authors, author_orcids = [], []
    for c in attrs.get("creators") or []:
        name = (" ".join(filter(None, [c.get("givenName"), c.get("familyName")]))
                or c.get("name") or "").strip()
        # DataCite "name" is often "Family, Given" — normalise the comma form.
        if "," in name:
            family, _, given = name.partition(",")
            name = f"{given.strip()} {family.strip()}".strip()
        if name:
            authors.append(name)
        for ident in c.get("nameIdentifiers") or []:
            if (ident.get("nameIdentifierScheme") or "").upper() == "ORCID":
                author_orcids.append(ident.get("nameIdentifier") or "")

    abstract = " ".join(
        d.get("description", "") for d in attrs.get("descriptions") or []
        if d.get("descriptionType") in (None, "Abstract"))

    return {
        "doi": doi,
        "title": title,
        "authors": authors,
        "author_orcids": author_orcids,
        "publication_year": int(attrs.get("publicationYear") or 0),
        "journal_name": (attrs.get("container") or {}).get("title")
                        or attrs.get("publisher")
                        or "Preprint or unindexed venue",
        "publication_type": "journal",
        "citation_count": int(attrs.get("citationCount") or 0),
        "abstract": _strip_jats(abstract)[:700],
    }


def _fetch_openalex_extras(doi: str) -> dict:
    """OpenAlex enrichment: the concept fingerprint (their ML-assigned
    concepts — a free analogue of a commercial fingerprint engine) plus any
    author ORCID iDs. Best-effort — an OpenAlex miss never blocks anything."""
    empty = {"concepts": [], "author_orcids": []}
    try:
        resp = httpx.get(f"{OPENALEX_API}/https://doi.org/{doi}",
                         headers=HEADERS, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            return empty
        work = resp.json()
    except (httpx.HTTPError, ValueError):
        return empty
    concepts = [
        c.get("display_name", "")
        for c in sorted(work.get("concepts") or [],
                        key=lambda c: c.get("score") or 0, reverse=True)
        if (c.get("score") or 0) >= 0.3
    ]
    orcids = [
        (a.get("author") or {}).get("orcid") or ""
        for a in work.get("authorships") or []
    ]
    return {"concepts": [c for c in concepts if c][:6],
            "author_orcids": [o for o in orcids if o]}


def fetch_doi_metadata(doi: str) -> dict:
    """Resolve a DOI: Crossref first, DataCite as fallback, then enrich with
    OpenAlex concepts + author ORCIDs. Raises SubmissionError when no
    registry knows the DOI.
    """
    doi = _norm_doi(doi)
    if not re.match(r"^10\.\d{4,9}/\S+$", doi):
        raise SubmissionError("That does not look like a valid DOI "
                              "(expected e.g. 10.1234/abcd.5678).")
    meta = _fetch_crossref(doi) or _fetch_datacite(doi)
    if meta is None:
        raise SubmissionError(
            "Neither Crossref nor DataCite has a record for that DOI.")
    extras = _fetch_openalex_extras(doi)
    meta["concepts"] = extras["concepts"]
    meta["author_orcids"] = (meta.get("author_orcids") or []) + extras["author_orcids"]
    return meta


# ---------------------------------------------------------------------------
# Authorship verification (the submitter must be an author of the paper)
# ---------------------------------------------------------------------------

# Transliteration variants + connector particles, same family as the ORCID
# verification so both identity checks agree.
_VARIANTS = {
    "rehman": "rahman", "rahmaan": "rahman",
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad",
    "muhammd": "muhammad", "mohd": "muhammad",
    "sayed": "syed", "sayyed": "syed",
    "husain": "hussain", "hussein": "hussain",
    "othman": "usman", "uthman": "usman",
    "fatimah": "fatima",
}
_PARTICLES = {"ur", "ul", "al", "bin", "binti", "ibn", "abu", "el", "de"}


def _norm_orcid_id(orcid: str) -> str:
    return re.sub(r"^https?://(www\.)?orcid\.org/", "", orcid.strip()).upper()


def _name_parts(name: str) -> tuple[set[str], set[str], set[str]]:
    """(identifying tokens, single-letter initials, first letters of ALL
    tokens including particles) for authorship matching. Particles count for
    initials — 'A. U. Rahman' abbreviates the 'Ur' in 'Arif Ur Rahman'."""
    name = re.sub(r"^(dr|mr|ms|mrs|prof|professor|engr)\.?\s+", "",
                  name.strip(), flags=re.I)
    raw = re.findall(r"[a-zA-Z]+", name.lower())
    full = {_VARIANTS.get(t, t) for t in raw
            if len(t) >= 2 and t not in _PARTICLES}
    initials = {t for t in raw if len(t) == 1}
    first_letters = {t[0] for t in raw}
    return full, initials, first_letters


def _author_matches(roster_name: str, author_name: str) -> bool:
    """Does this paper author plausibly equal this roster researcher?

    Handles initials ("A. Rahman"), missing middle names, particles, and
    transliteration variants. A single shared surname alone is NOT enough —
    it must be backed by compatible initials.
    """
    r_full, _, r_letters = _name_parts(roster_name)
    a_full, a_init, _ = _name_parts(author_name)
    if not r_full or not a_full:
        return False
    if len(r_full & a_full) >= 2:
        return True
    # One name contained in the other, both carrying 2+ identifying tokens
    # ("Arif Rahman" vs "Arif Ur Rahman Khan").
    if (r_full <= a_full or a_full <= r_full) and min(len(r_full), len(a_full)) >= 2:
        return True
    # Initials style ("A. Rahman", "A. U. Rahman"): shared surname + every
    # initial matches the first letter of some roster token (particles too).
    if r_full & a_full and a_init:
        return a_init <= r_letters
    return False


def verify_authorship(meta: dict, submitter: dict,
                      submitter_orcid: str | None) -> str:
    """Confirm the submitter is an author of the paper described by meta.

    Returns how they matched ("orcid" or "name"); raises SubmissionError when
    they do not appear in the author list. Mirrors the attribution guard the
    bulk OpenAlex pipeline applies, so both ingestion paths share one
    integrity standard.
    """
    if submitter_orcid:
        paper_orcids = {_norm_orcid_id(o)
                        for o in meta.get("author_orcids") or [] if o}
        if _norm_orcid_id(submitter_orcid) in paper_orcids:
            return "orcid"
    for name in meta.get("authors") or []:
        if _author_matches(submitter["full_name"], name):
            return "name"
    shown = ", ".join((meta.get("authors") or [])[:6]) or "no public author list"
    raise SubmissionError(
        f"Your name does not appear in this paper's author list ({shown}). "
        f"You can only add publications you authored.")


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicate(doi: str | None, title: str) -> dict | None:
    """Return the existing publication matching this DOI or title, if any."""
    doi_norm = _norm_doi(doi) if doi else None
    title_norm = _norm_title(title)
    for p in loader.load("publications"):
        if doi_norm and p.get("doi") and _norm_doi(p["doi"]) == doi_norm:
            return p
        if title_norm and _norm_title(p.get("title", "")) == title_norm:
            return p
    return None


# ---------------------------------------------------------------------------
# Record building + persistence
# ---------------------------------------------------------------------------

def _topics_for(title: str, abstract: str,
                concepts: list[str] | None = None) -> list[dict]:
    """Match the publication text against the topic catalogue keywords.

    OpenAlex concepts (the DOI's ML-assigned fingerprint) are folded into the
    matching text, so a paper whose title never says "deep learning" still
    lands in the right topic when its concepts do.
    """
    from scripts.build_seed import TOPIC_CATALOGUE  # same source as pipeline

    topic_ids = {t["topic_name"]: t["topic_id"] for t in loader.load("topics")}
    concept_text = " ".join(concepts or [])
    text = f" {title.lower()} {abstract.lower()} {concept_text.lower()} "
    chosen = []
    for name, _icon, keywords in TOPIC_CATALOGUE:
        if name in topic_ids and any(k in text for k in keywords):
            chosen.append({"topic_id": topic_ids[name], "topic_name": name})
        if len(chosen) >= 2:
            break
    return chosen


def _link_authors(author_names: list[str], submitter: dict) -> list[dict]:
    """Link author names to the researcher roster. The submitter is linked to
    THEIR OWN entry in the paper's author list (matched fuzzily — initials,
    variants), never appended as an extra author. Only the manual path, which
    has no author metadata at all, records the submitter directly."""
    roster = {_name_key(r["full_name"]): r["researcher_id"]
              for r in loader.load("researchers")}
    authors, linked_ids = [], set()
    for order, name in enumerate(author_names[:12], start=1):
        rid = roster.get(_name_key(name))
        # The submitter's name on the paper may differ from the roster form
        # ("A. Rahman" / "Arif Rahman") — claim exactly one matching entry.
        if (rid is None and submitter["researcher_id"] not in linked_ids
                and _author_matches(submitter["full_name"], name)):
            rid = submitter["researcher_id"]
        if rid is not None:
            linked_ids.add(rid)
        authors.append({"researcher_id": rid, "full_name": name, "order": order})
    if not author_names:
        # Manual entry (no metadata): the submitter records their own paper.
        authors.append({
            "researcher_id": submitter["researcher_id"],
            "full_name": submitter["full_name"],
            "order": 1,
        })
    return authors


def _persist(record: dict) -> dict:
    """Append the record to publications.json + submitted_publications.json."""
    pubs_path = DATA_DIR / "publications.json"
    pubs = json.loads(pubs_path.read_text("utf-8")) if pubs_path.exists() else []
    record["publication_id"] = max(
        (p["publication_id"] for p in pubs), default=0) + 1
    pubs.append(record)
    pubs_path.write_text(
        json.dumps(pubs, indent=2, ensure_ascii=False), "utf-8")

    submitted_path = DATA_DIR / "submitted_publications.json"
    submitted = (json.loads(submitted_path.read_text("utf-8"))
                 if submitted_path.exists() else [])
    submitted.append(record)
    submitted_path.write_text(
        json.dumps(submitted, indent=2, ensure_ascii=False), "utf-8")

    # Refresh every cached view of the data.
    loader.clear_cache()
    from app.services.rag import authored
    authored._Store.reset()
    return record


def _index_chunk(record: dict) -> None:
    """Embed one publication fact-card into the live RAG index (same format
    as scripts.build_index.publication_chunks) so the chatbot knows it."""
    import numpy as np

    from app.services.rag.retriever import (DATA_DIR as INDEX_DIR,
                                            EMBED_MODEL, MODEL_CACHE,
                                            Retriever)

    authors = ", ".join(a["full_name"] for a in record["authors"][:8])
    text = (
        f"Publication: \"{record['title']}\" ({record['publication_year']}), "
        f"{record['publication_type']} in {record['journal_name']}. "
        f"Authors: {authors}. Citations: {record['citation_count']}. "
        f"Campus: {record['campus']}."
    )
    if record.get("doi"):
        text += f" DOI: {record['doi']}."
    chunk = {
        "text": text,
        "kind": "publication",
        "ref_id": record["publication_id"],
        "label": f"{record['title'][:70]} ({record['publication_year']})",
    }

    from fastembed import TextEmbedding  # deferred: slow import

    model = TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))
    vec = np.array(list(model.embed([chunk["text"]])), dtype=np.float32)
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)

    chunks = json.loads((INDEX_DIR / "rag_chunks.json").read_text("utf-8"))
    existing = np.load(INDEX_DIR / "rag_index.npz")["vectors"]
    chunks.append(chunk)
    (INDEX_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8")
    np.savez_compressed(INDEX_DIR / "rag_index.npz",
                        vectors=np.vstack([existing, vec]))
    Retriever.reset()


def _bump_researcher_counts(record: dict) -> None:
    path = DATA_DIR / "researchers.json"
    researchers = json.loads(path.read_text("utf-8"))
    linked = {a["researcher_id"] for a in record["authors"]
              if a.get("researcher_id") is not None}
    for r in researchers:
        if r["researcher_id"] in linked:
            r["publication_count"] = r.get("publication_count", 0) + 1
            r["citation_count"] = (r.get("citation_count", 0)
                                   + record.get("citation_count", 0))
    path.write_text(json.dumps(researchers, indent=2, ensure_ascii=False),
                    "utf-8")
    loader.clear_cache()


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def preview_doi(doi: str, submitter: dict | None = None,
                submitter_orcid: str | None = None) -> dict:
    """Metadata preview for the verify step: duplicates, the topic
    fingerprint, and the authorship verdict (so the user learns they cannot
    submit someone else's paper BEFORE clicking confirm)."""
    meta = fetch_doi_metadata(doi)
    dup = find_duplicate(meta["doi"], meta["title"])
    topics = _topics_for(meta["title"], meta.get("abstract", ""),
                         meta.get("concepts"))
    authorship_ok, authorship_message = True, None
    if submitter is not None:
        try:
            verify_authorship(meta, submitter, submitter_orcid)
        except SubmissionError as exc:
            authorship_ok, authorship_message = False, str(exc)
    return {**meta, "duplicate": bool(dup),
            "duplicate_of": dup["title"] if dup else None,
            "topics": [t["topic_name"] for t in topics],
            "authorship_ok": authorship_ok,
            "authorship_message": authorship_message}


def submit_doi(doi: str, submitter: dict,
               submitter_orcid: str | None = None) -> dict:
    """Create a publication from a DOI for the submitting researcher.

    The submitter must appear in the paper's author list (ORCID or name
    match) — the same attribution standard as the bulk pipeline."""
    meta = fetch_doi_metadata(doi)
    if find_duplicate(meta["doi"], meta["title"]):
        raise SubmissionError(
            "This publication is already in the database.")
    verify_authorship(meta, submitter, submitter_orcid)
    return _create(meta, submitter, source="doi")


def submit_manual(title: str, journal_name: str, publication_year: int,
                  publication_type: str, submitter: dict) -> dict:
    """Create a publication from manually entered details (no DOI)."""
    title = title.strip()
    if find_duplicate(None, title):
        raise SubmissionError("A publication with this title already exists.")
    meta = {
        "doi": None,
        "title": title,
        "authors": [],
        "publication_year": publication_year,
        "journal_name": journal_name.strip() or "Preprint or unindexed venue",
        "publication_type": (publication_type
                             if publication_type in ("journal", "conference")
                             else "journal"),
        "citation_count": 0,
        "abstract": "",
    }
    return _create(meta, submitter, source="manual")


def _create(meta: dict, submitter: dict, source: str) -> dict:
    authors = _link_authors(meta.get("authors", []), submitter)
    if not any(a.get("researcher_id") == submitter["researcher_id"]
               for a in authors):
        # Verified as an author (e.g. by ORCID) but the name form on the
        # paper defeated fuzzy matching — record the attribution explicitly.
        authors.append({
            "researcher_id": submitter["researcher_id"],
            "full_name": submitter["full_name"],
            "order": len(authors) + 1,
        })
    record = {
        "publication_id": 0,  # assigned in _persist
        "title": meta["title"],
        "abstract": meta.get("abstract", ""),
        "doi": meta.get("doi"),
        "publication_year": meta["publication_year"],
        "journal_name": meta["journal_name"],
        "publication_type": meta["publication_type"],
        "citation_count": meta.get("citation_count", 0),
        "campus": submitter.get("campus", ""),
        "authors": authors,
        "topics": _topics_for(meta["title"], meta.get("abstract", ""),
                              meta.get("concepts")),
        "source": source,
    }
    record = _persist(record)
    _bump_researcher_counts(record)
    try:
        _index_chunk(record)
    except Exception:  # noqa: BLE001 - the record is saved; index can rebuild
        pass
    return record
