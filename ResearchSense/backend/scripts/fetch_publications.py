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
from scripts.fetch_enrichment import (backfill_topic_names,
                                      derive_research_areas,
                                      expertise_field_guard,
                                      international_of, merge_supplementary)
from scripts.fetch_sources import (country_from_affiliation, crossref_works_for,
                                   s2_works_for)

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
INSTITUTION = "I59225215"  # Bahria University in OpenAlex
API = "https://api.openalex.org"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
MAX_WORKS = 25  # per researcher, most cited first


def _key(name: str) -> str:
    name = re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s*", "", name.strip().lower())
    return re.sub(r"[^a-z]", "", name)


# --- Fuzzy co-author matching (second pass) -------------------------------
# Exact name-key equality misses initials ("M. A. Khan"), transliteration
# variants (Rehman/Rahman) and dropped middle names, which left most internal
# co-authorships unlinked. Same matcher family as the portal's authorship
# verification (unit-tested there).

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


def _name_parts(name: str) -> tuple[set, set, set]:
    name = re.sub(r"^(dr|mr|ms|mrs|prof|professor|engr)\.?\s+", "",
                  name.strip(), flags=re.I)
    raw = re.findall(r"[a-zA-Z]+", name.lower())
    full = {_VARIANTS.get(t, t) for t in raw
            if len(t) >= 2 and t not in _PARTICLES}
    initials = {t for t in raw if len(t) == 1}
    first_letters = {t[0] for t in raw}
    return full, initials, first_letters


def _fuzzy_name_match(roster_name: str, author_name: str) -> bool:
    r_full, _, r_letters = _name_parts(roster_name)
    a_full, a_init, _ = _name_parts(author_name)
    if not r_full or not a_full:
        return False
    if len(r_full & a_full) >= 2:
        return True
    if (r_full <= a_full or a_full <= r_full) and min(len(r_full), len(a_full)) >= 2:
        return True
    if r_full & a_full and a_init:
        return a_init <= r_letters
    return False


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
    expertise_of = {r["researcher_id"]:
                    f"{r.get('expertise','')} {r.get('department','')}"
                    for r in researchers}

    print("Fetching Bahria University works from OpenAlex...")
    all_works = institution_works()
    print(f"  pulled {len(all_works)} Bahria affiliated works")

    publications = []
    pub_stats: dict[int, list[int]] = {r["researcher_id"]: [] for r in researchers}
    for pid, w in enumerate(sorted(
            all_works, key=lambda x: x.get("cited_by_count", 0),
            reverse=True), start=1):
        work_topics = topics_for_work(w.get("title", ""), w.get("concepts", []), topic_ids)
        oa_topic_names = [t.get("display_name", "")
                          for t in (w.get("topics") or [])[:3]]
        authorships = w.get("authorships", [])
        institutions: list[dict] = []
        for a in authorships:
            for inst in a.get("institutions") or []:
                entry = {"name": inst.get("display_name", ""),
                         "country": inst.get("country_code")}
                if entry["name"] and entry not in institutions:
                    institutions.append(entry)
        authors = []
        matched_ids = []
        for order, a in enumerate(authorships, start=1):
            disp = a.get("author", {}).get("display_name", "").strip()
            rid = roster.get(_key(disp))
            # Link only when the paper is Bahria affiliated for this author AND
            # its field overlaps the researcher's real expertise.
            guard_text = (expertise_of.get(rid, "") if rid is not None else "")
            link = (rid is not None and author_at_bahria(a)
                    and expertise_field_guard(
                        oa_topic_names or [t["topic_name"] for t in work_topics],
                        guard_text))
            if link and rid not in matched_ids:
                matched_ids.append(rid)
            authors.append({"researcher_id": rid if link else None,
                            "full_name": disp, "order": order})

        # Fuzzy second pass for authors exact matching missed (initials,
        # variants, dropped middle names). Safety rules: the author must be
        # Bahria-affiliated on THIS paper, exactly ONE roster researcher may
        # match the name (ambiguity -> no link), and the field guard applies
        # unless another roster author already anchors the paper (an internal
        # co-authorship is strong evidence the fuzzy match is right).
        for i, a in enumerate(authorships):
            if authors[i]["researcher_id"] is not None or not author_at_bahria(a):
                continue
            disp = authors[i]["full_name"]
            cands = [r for r in researchers
                     if _fuzzy_name_match(r["full_name"], disp)]
            if len(cands) != 1:
                continue
            rid = cands[0]["researcher_id"]
            if rid in matched_ids:
                continue
            anchored = bool(matched_ids)
            if not anchored and not expertise_field_guard(
                    oa_topic_names or [t["topic_name"] for t in work_topics],
                    expertise_of.get(rid, "")):
                continue
            authors[i]["researcher_id"] = rid
            matched_ids.append(rid)

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
            "topic_names": oa_topic_names,
            "coauthor_institutions": institutions,
            "international": international_of(institutions),
            "source": "openalex",
        })

    # Supplementary sources for researchers OpenAlex barely covers.
    covered = {rid for rid, cites in pub_stats.items() if len(cites) >= 3}
    thin = [r for r in researchers if r["researcher_id"] not in covered]
    print(f"  querying Semantic Scholar/Crossref for {len(thin)} researchers")
    extra_norm: list[dict] = []
    for r in thin:
        for rec in (s2_works_for(r["full_name"])
                    + crossref_works_for(r["full_name"])):
            names = rec["topic_names"]
            if not expertise_field_guard(
                    names, f"{r.get('expertise','')} {r.get('department','')}"):
                continue
            insts = []
            for a in rec["authors"]:
                code = country_from_affiliation(a.get("affiliation", ""))
                nm = (a.get("affiliation") or "").split(";")[0].strip()
                if nm and {"name": nm, "country": code} not in insts:
                    insts.append({"name": nm, "country": code})
            extra_norm.append({
                "publication_id": 0,
                "title": clean_title(rec["title"]),
                "abstract": "",
                "doi": rec["doi"],
                "publication_year": rec["publication_year"],
                "journal_name": rec["journal_name"],
                "publication_type": rec["publication_type"],
                "citation_count": rec["citation_count"],
                "campus": r.get("campus", ""),
                "authors": [{"researcher_id":
                             (r["researcher_id"]
                              if _fuzzy_name_match(r["full_name"], a["full_name"])
                              else None),
                             "full_name": a["full_name"], "order": o}
                            for o, a in enumerate(rec["authors"][:12], start=1)],
                "topics": [],
                "topic_names": names,
                "coauthor_institutions": insts,
                "international": international_of(insts),
                "source": rec["source"],
            })
        time.sleep(1.0)  # unauthenticated S2/Crossref rate courtesy
    before = len(publications)
    publications = merge_supplementary(publications, extra_norm)
    for p in publications[before:]:
        p["publication_id"] = 0  # renumbered below
        for a in p["authors"]:
            if a["researcher_id"] is not None:
                pub_stats[a["researcher_id"]].append(p["citation_count"])
    for i, p in enumerate(publications, start=1):
        p["publication_id"] = i
    print(f"  +{len(publications) - before} from supplementary sources")

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

    # Backfill topic_names for faculty-submitted publications (they carry only
    # the legacy `topics` list, never topic_names) so they count toward
    # research-area derivation below and keep an id in the dynamic
    # topics.json rebuild instead of being wiped by the topics rewrite.
    backfilled_names: set[str] = {
        t["topic_name"] for p in publications
        if not p.get("topic_names") and p.get("topics")
        for t in p["topics"]
    }
    backfill_topic_names(publications)

    # Hybrid research areas + international partners (SRS 2, 6).
    pubs_of: dict[int, list[dict]] = {r["researcher_id"]: [] for r in researchers}
    for p in publications:
        for a in p.get("authors", []):
            rid = a.get("researcher_id")
            if rid in pubs_of:
                pubs_of[rid].append(p)
    for r in researchers:
        mine = pubs_of[r["researcher_id"]]
        r["research_areas"] = derive_research_areas(r, mine)
        partners: list[dict] = []
        for p in mine:
            for inst in p.get("coauthor_institutions", []):
                code = inst.get("country")
                if code and code != "PK":
                    entry = {"institution": inst["name"], "country": code}
                    if entry not in partners:
                        partners.append(entry)
        r["international_collaborations"] = partners

    # Dynamic topic index from the union of derived areas (SRS 2).
    area_names: dict[str, int] = {}
    for r in researchers:
        for name in r["research_areas"]:
            area_names.setdefault(name, len(area_names) + 1)
    for name in backfilled_names:
        area_names.setdefault(name, len(area_names) + 1)
    topics = [{"topic_id": tid, "topic_name": name, "icon": "sparkles",
               "description": f"Research and expertise in {name}.",
               "source": "derived",
               "researcher_count": sum(1 for r in researchers
                                       if name in r["research_areas"]),
               "publication_count": sum(1 for p in publications
                                        if name in (p.get("topic_names") or []))}
              for name, tid in area_names.items()]
    name_to_id = dict(area_names)
    for r in researchers:
        r["topics"] = [{"topic_id": name_to_id[n], "topic_name": n}
                       for n in r["research_areas"]]
    for p in publications:
        p["topics"] = [{"topic_id": name_to_id[n], "topic_name": n}
                       for n in (p.get("topic_names") or [])
                       if n in name_to_id][:4]

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
