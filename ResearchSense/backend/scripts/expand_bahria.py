"""Extend coverage to every Bahria-affiliated author and paper in OpenAlex.

`fetch_publications` keeps a paper only when one of its authors is on the
scraped faculty roster. Bahria has ~5,900 publishing authors and the roster has
358, so roughly three quarters of the institution's papers were fetched and
then thrown away — and a Bahria researcher who is not on the roster could not
find their own work in the portal at all.

This script runs *after* the existing pipeline and only ever adds:

  A. papers whose authors are already on the roster but which were dropped
     (the field guard is skipped here — the author match plus the Bahria
     affiliation on that paper is evidence enough), and
  B. the remaining Bahria-affiliated authors, as profiles marked
     ``source: "openalex"``.

Curated profiles are never modified beyond their publication and citation
counts, so the scraped directory stays authoritative. Extended profiles carry
only what OpenAlex actually knows — a name and a publication record — so they
are excluded from the campus/department analytics and from the default
directory listing, while remaining fully searchable and answerable by the
assistant. That is the point: any Bahria individual can find their own work.

Re-running is safe: authors are keyed by their OpenAlex id and papers by DOI or
normalised title, so nothing is duplicated.

Run (from backend/), after fetch_publications:

    python -m scripts.expand_bahria
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
INSTITUTION = "I59225215"  # Bahria University in OpenAlex
API = "https://api.openalex.org"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}

# Papers before this are too sparsely recorded to be useful (matches the
# existing pipeline's window).
FROM_DATE = "2008-01-01"

# Only these fields are needed; asking for fewer makes the sweep much faster.
SELECT = (
    "id,doi,title,publication_year,cited_by_count,authorships,"
    "primary_location,type,topics"
)


def _key(name: str) -> str:
    """Normalised name used to match an OpenAlex author to a roster entry."""
    name = re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s*", "", name.strip().lower())
    return re.sub(r"[^a-z]", "", name)


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _get(path: str, params: dict) -> dict:
    for _attempt in range(3):
        try:
            r = httpx.get(f"{API}{path}", params=params, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(1.5)
    return {"results": [], "meta": {}}


def institution_works() -> list[dict]:
    """Every Bahria-affiliated work, via one cursor sweep (~2.5 minutes)."""
    works: list[dict] = []
    cursor = "*"
    while cursor:
        data = _get(
            "/works",
            {
                "filter": (
                    f"authorships.institutions.id:{INSTITUTION},"
                    f"from_publication_date:{FROM_DATE}"
                ),
                "per_page": 200,
                "cursor": cursor,
                "select": SELECT,
            },
        )
        results = data.get("results", [])
        works.extend(results)
        if not results:
            break
        cursor = data.get("meta", {}).get("next_cursor")
        print(f"\r  {len(works)} works...", end="", flush=True)
    print()
    return works


def at_bahria(authorship: dict) -> bool:
    """True when this author was credited to Bahria on this paper."""
    return any(
        (inst.get("id") or "").endswith(INSTITUTION)
        for inst in authorship.get("institutions") or []
    )


def venue_of(work: dict) -> tuple[str, str]:
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    name = (source.get("display_name") or "").strip()
    wtype = work.get("type") or "journal"
    if wtype not in ("journal-article", "proceedings-article", "book-chapter", "book"):
        wtype = "journal"
    kind = {
        "journal-article": "journal",
        "proceedings-article": "conference",
        "book-chapter": "book-chapter",
        "book": "book",
    }.get(wtype, "journal")
    return name, kind


def main() -> None:
    researchers = json.loads((DATA_DIR / "researchers.json").read_text("utf-8"))
    publications = json.loads((DATA_DIR / "publications.json").read_text("utf-8"))

    before_r, before_p = len(researchers), len(publications)
    print(f"Starting from {before_r} researchers and {before_p} publications.")

    print("Sweeping every Bahria work in OpenAlex...")
    t0 = time.time()
    works = institution_works()
    print(f"  {len(works)} works in {time.time() - t0:.0f}s")

    # --- existing state, so a re-run adds nothing twice --------------------
    by_key = {_key(r["full_name"]): r for r in researchers}
    by_openalex = {r["openalex_id"]: r for r in researchers if r.get("openalex_id")}
    seen_dois = {(p.get("doi") or "").lower() for p in publications if p.get("doi")}
    seen_titles = {_norm_title(p.get("title", "")) for p in publications}
    next_rid = max(r["researcher_id"] for r in researchers) + 1
    next_pid = max(p["publication_id"] for p in publications) + 1

    added_researchers = 0
    added_publications = 0

    # Most cited first, so the best-known work takes the lowest ids.
    for work in sorted(works, key=lambda w: w.get("cited_by_count", 0), reverse=True):
        title = (work.get("title") or "").strip()
        if not title:
            continue
        doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()

        authors = []
        linked_any = False
        for order, a in enumerate(work.get("authorships", []), start=1):
            name = ((a.get("author") or {}).get("display_name") or "").strip()
            if not name:
                continue
            rid = None
            if at_bahria(a):
                oa_id = ((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
                existing = by_openalex.get(oa_id) or by_key.get(_key(name))
                if existing is not None:
                    rid = existing["researcher_id"]
                    # Remember the OpenAlex id on a curated profile the first
                    # time we see it, so later runs match on id, not spelling.
                    if oa_id and not existing.get("openalex_id"):
                        existing["openalex_id"] = oa_id
                        by_openalex[oa_id] = existing
                else:
                    # B: a Bahria author the roster never had.
                    profile = {
                        "researcher_id": next_rid,
                        "full_name": name,
                        "designation": "",
                        "academic_rank": "",
                        "department": "",
                        "campus": "",
                        "institution": "Bahria University",
                        "email": None,
                        "orcid_id": None,
                        "openalex_id": oa_id or None,
                        "photo_url": None,
                        "expertise": "",
                        "publication_count": 0,
                        "citation_count": 0,
                        "topics": [],
                        "research_areas": [],
                        "profile_bio": "",
                        "education": "",
                        # Marks a profile built from the publication record
                        # alone: no department, campus, or biography exists.
                        "source": "openalex",
                    }
                    researchers.append(profile)
                    by_key.setdefault(_key(name), profile)
                    if oa_id:
                        by_openalex[oa_id] = profile
                    rid = next_rid
                    next_rid += 1
                    added_researchers += 1
                linked_any = True
            authors.append({"researcher_id": rid, "full_name": name, "order": order})

        if not linked_any:
            continue
        if (doi and doi in seen_dois) or _norm_title(title) in seen_titles:
            continue

        venue, kind = venue_of(work)
        topic_names = [
            (t.get("display_name") or "").strip()
            for t in (work.get("topics") or [])[:3]
            if t.get("display_name")
        ]
        # Campus is a Bahria-directory fact; OpenAlex does not record it. It is
        # filled in below only when a curated author anchors the paper.
        publications.append(
            {
                "publication_id": next_pid,
                "title": title,
                "abstract": "",
                "doi": doi or None,
                "publication_year": work.get("publication_year") or 0,
                "publication_date": None,
                "journal_name": venue,
                "publication_type": kind,
                "citation_count": work.get("cited_by_count", 0),
                "campus": "",
                "authors": authors,
                "topics": [],
                "topic_names": topic_names,
                "coauthor_institutions": [],
                "international": False,
                "source": "openalex-extended",
            }
        )
        if doi:
            seen_dois.add(doi)
        seen_titles.add(_norm_title(title))
        next_pid += 1
        added_publications += 1

    # --- campus for the new papers, where a curated author anchors them ----
    campus_of = {
        r["researcher_id"]: r.get("campus", "")
        for r in researchers
        if r.get("source") != "openalex"
    }
    for p in publications:
        if p.get("campus"):
            continue
        for a in p.get("authors", []):
            campus = campus_of.get(a.get("researcher_id") or -1)
            if campus:
                p["campus"] = campus
                break

    # --- research areas for extended profiles ------------------------------
    # OpenAlex gives no department or expertise text, so without this an
    # extended profile says nothing about what its owner works on — the
    # assistant cannot answer "what does X research?" and the profile page is
    # blank. Their papers' own topics are the honest answer.
    from collections import Counter

    topics_by_author: dict[int, Counter] = {}
    for p_rec in publications:
        names = p_rec.get("topic_names") or []
        if not names:
            continue
        for a in p_rec.get("authors", []):
            rid = a.get("researcher_id")
            if rid is not None:
                topics_by_author.setdefault(rid, Counter()).update(names)

    for r in researchers:
        if r.get("source") != "openalex":
            continue
        top = [
            name
            for name, _n in topics_by_author.get(
                r["researcher_id"], Counter()
            ).most_common(5)
        ]
        r["research_areas"] = top
        r["expertise"] = ", ".join(top)

    # --- recount every profile from the final publication table ------------
    counts: dict[int, list[int]] = {}
    for p in publications:
        for a in p.get("authors", []):
            rid = a.get("researcher_id")
            if rid is not None:
                counts.setdefault(rid, []).append(int(p.get("citation_count") or 0))
    for r in researchers:
        cites = counts.get(r["researcher_id"], [])
        r["publication_count"] = len(cites)
        r["citation_count"] = sum(cites)

    (DATA_DIR / "researchers.json").write_text(
        json.dumps(researchers, ensure_ascii=False, indent=2), "utf-8"
    )
    (DATA_DIR / "publications.json").write_text(
        json.dumps(publications, ensure_ascii=False, indent=2), "utf-8"
    )

    curated = sum(1 for r in researchers if r.get("source") != "openalex")
    empty_curated = sum(
        1
        for r in researchers
        if r.get("source") != "openalex" and not r["publication_count"]
    )
    print()
    print(f"researchers : {before_r} -> {len(researchers)} (+{added_researchers})")
    print(f"  curated   : {curated}   extended: {len(researchers) - curated}")
    print(f"  curated profiles still with no papers: {empty_curated}")
    print(f"publications: {before_p} -> {len(publications)} (+{added_publications})")
    print("\nRebuild the index next:  python -m scripts.build_index")


if __name__ == "__main__":
    main()
