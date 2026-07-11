"""Fetch real publications for Bahria E-8 researchers from the OpenAlex API.

OpenAlex (openalex.org) is a free and open scholarly database with no key
required. For each researcher this script finds the matching OpenAlex author
(filtered to the Bahria University institution), pulls their works, links
co-authors back to our roster, and writes real publications.

It also updates each researcher's publication and citation counts and the topic
counts from the real works. Run after build_seed:

    python -m scripts.fetch_publications
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from scripts.build_seed import TOPIC_CATALOGUE

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
INSTITUTION = "I59225215"  # Bahria University in OpenAlex
API = "https://api.openalex.org"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
MAX_WORKS = 25  # per researcher, most cited first


def _key(name: str) -> str:
    name = re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s*", "", name.strip().lower())
    return re.sub(r"[^a-z]", "", name)


def clean_title(title: str) -> str:
    """Strip LaTeX math and markup that OpenAlex sometimes leaves in titles."""
    if not title:
        return "Untitled"
    title = re.sub(r"\$+[^$]*\$+", "", title)   # $...$ and $$...$$ math
    title = re.sub(r"\\[a-zA-Z]+", " ", title)   # \command
    title = re.sub(r"[{}\\]", "", title)          # stray braces and slashes
    title = re.sub(r"\s+([,.;:)])", r"\1", title)
    return re.sub(r"\s+", " ", title).strip()


def _get(path: str, params: dict) -> dict:
    for attempt in range(3):
        try:
            r = httpx.get(f"{API}{path}", params=params, headers=HEADERS, timeout=40)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(1.5)
    return {"results": [], "meta": {"count": 0}}


def institution_works() -> list[dict]:
    """Page through every work affiliated with Bahria University.

    Matching against the institution keeps famous namesakes out: we only ever
    link a paper to a researcher when that paper is Bahria affiliated.
    """
    works, cursor = [], "*"
    while cursor:
        data = _get("/works", {
            "filter": f"authorships.institutions.id:{INSTITUTION},"
                      f"from_publication_date:2008-01-01",
            "per_page": 200, "cursor": cursor,
        })
        results = data.get("results", [])
        works.extend(results)
        cursor = data.get("meta", {}).get("next_cursor")
        if not results:
            break
        time.sleep(0.2)
    return works


def author_at_bahria(authorship: dict) -> bool:
    return any(INSTITUTION in (inst.get("id") or "")
              for inst in authorship.get("institutions", []))


def topics_for_work(title: str, concepts: list[dict], topic_ids: dict) -> list[dict]:
    text = " " + (title or "").lower() + " "
    text += " ".join(c.get("display_name", "").lower() for c in concepts)
    chosen = []
    for name, _icon, keywords in TOPIC_CATALOGUE:
        if any(k in text for k in keywords):
            chosen.append({"topic_id": topic_ids[name], "topic_name": name})
        if len(chosen) >= 2:
            break
    return chosen


def venue_of(work: dict) -> tuple[str, str]:
    loc = (work.get("primary_location") or {}).get("source") or {}
    name = loc.get("display_name") or "Preprint or unindexed venue"
    wtype = "conference" if work.get("type") == "proceedings-article" else "journal"
    return name, wtype


def main() -> None:
    researchers = json.loads((DATA_DIR / "researchers.json").read_text("utf-8"))
    topics = json.loads((DATA_DIR / "topics.json").read_text("utf-8"))
    topic_ids = {t["topic_name"]: t["topic_id"] for t in topics}
    roster = {_key(r["full_name"]): r["researcher_id"] for r in researchers}
    campus_of = {r["researcher_id"]: r.get("campus", "") for r in researchers}
    # Field guard: a paper is only attributed to a researcher when its field
    # overlaps that researcher's real expertise. This removes same-name authors
    # from other fields at the same university (a common source of error).
    researcher_topics = {
        r["researcher_id"]: {t["topic_id"] for t in r["topics"]}
        for r in researchers
    }

    print("Fetching Bahria University works from OpenAlex...")
    all_works = institution_works()
    print(f"  pulled {len(all_works)} Bahria affiliated works")

    publications = []
    pub_stats: dict[int, list[int]] = {r["researcher_id"]: [] for r in researchers}
    for pid, w in enumerate(sorted(
            all_works, key=lambda x: x.get("cited_by_count", 0),
            reverse=True), start=1):
        work_topics = topics_for_work(w.get("title", ""), w.get("concepts", []), topic_ids)
        work_topic_ids = {t["topic_id"] for t in work_topics}
        authorships = w.get("authorships", [])
        authors = []
        matched_ids = []
        for order, a in enumerate(authorships, start=1):
            disp = a.get("author", {}).get("display_name", "").strip()
            rid = roster.get(_key(disp))
            # Link only when the paper is Bahria affiliated for this author AND
            # its field overlaps the researcher's real expertise.
            link = (rid is not None and author_at_bahria(a)
                    and bool(researcher_topics.get(rid, set()) & work_topic_ids))
            if link and rid not in matched_ids:
                matched_ids.append(rid)
            authors.append({"researcher_id": rid if link else None,
                            "full_name": disp, "order": order})
        if not matched_ids:
            continue
        venue, wtype = venue_of(w)
        cited = w.get("cited_by_count", 0)
        for rid in matched_ids:
            pub_stats[rid].append(cited)
        publications.append({
            "publication_id": len(publications) + 1,
            "title": clean_title(w.get("title") or w.get("display_name") or ""),
            "abstract": "",
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "publication_year": w.get("publication_year") or 0,
            "journal_name": venue,
            "publication_type": wtype,
            "citation_count": cited,
            "campus": campus_of.get(matched_ids[0], ""),
            "authors": authors[:12],
            "topics": work_topics,
            "source": "openalex",
        })

    # Re-merge faculty-submitted publications (DOI-based / manual entries from
    # the portal) so a refresh never wipes them. Dedupe by DOI, then title.
    submitted_path = DATA_DIR / "submitted_publications.json"
    if submitted_path.exists():
        submitted = json.loads(submitted_path.read_text("utf-8"))
        have_dois = {(p.get("doi") or "").lower() for p in publications if p.get("doi")}
        have_titles = {re.sub(r"[^a-z0-9]", "", p["title"].lower())
                       for p in publications}
        merged = 0
        for s in submitted:
            doi = (s.get("doi") or "").lower()
            title_key = re.sub(r"[^a-z0-9]", "", s["title"].lower())
            if (doi and doi in have_dois) or title_key in have_titles:
                continue  # OpenAlex now covers it — keep the fetched version
            s["publication_id"] = len(publications) + 1
            publications.append(s)
            for a in s.get("authors", []):
                rid = a.get("researcher_id")
                if rid in pub_stats:
                    pub_stats[rid].append(s.get("citation_count", 0))
            merged += 1
        if merged:
            print(f"  re-merged {merged} faculty-submitted publication(s)")

    # Update researcher counts from real works.
    for r in researchers:
        cites = pub_stats.get(r["researcher_id"], [])
        r["publication_count"] = len(cites)
        r["citation_count"] = sum(cites)

    # Recompute topic counts from real publications.
    for t in topics:
        t["publication_count"] = sum(
            1 for p in publications if any(pt["topic_id"] == t["topic_id"] for pt in p["topics"]))

    (DATA_DIR / "publications.json").write_text(
        json.dumps(publications, indent=2, ensure_ascii=False), "utf-8")
    (DATA_DIR / "researchers.json").write_text(
        json.dumps(researchers, indent=2, ensure_ascii=False), "utf-8")
    (DATA_DIR / "topics.json").write_text(
        json.dumps(topics, indent=2, ensure_ascii=False), "utf-8")

    linked = sum(1 for r in researchers if r["publication_count"])
    print(f"Wrote {len(publications)} real publications.")
    print(f"  {linked}/{len(researchers)} researchers now have real publications.")
    top = max(researchers, key=lambda r: r["citation_count"])
    print(f"  most cited: {top['full_name']} ({top['citation_count']} citations)")


if __name__ == "__main__":
    main()
