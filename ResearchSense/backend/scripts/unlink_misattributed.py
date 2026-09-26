"""Remove authorship links whose printed name belongs to someone else.

The fetch step's fuzzy matcher credited a paper to a faculty profile when
two name words agreed (see scripts/author_identity.py for what went wrong
and the rule that replaces it). This pass applies that rule to the data
already built:

* every link from a paper to a directory profile whose printed author name
  does not fit the profile is removed (the author stays on the paper by
  name; nothing is deleted), and written to ``author_unlinks.json``;
* every directory profile's paper and citation counts are recomputed from
  the papers it now lists, so a profile never claims work it does not show;
* the research areas, topic links and international partners of profiles
  that lost papers are derived again from what remains, reusing existing
  topic ids so area links keep working, and the head count of each area
  they left or joined is updated.

Publication-only author records (``source == "openalex"``) come from
OpenAlex author ids rather than name matching, so they are left alone.
Idempotent: a second run changes nothing.

    python -m scripts.unlink_misattributed          # dry run
    python -m scripts.unlink_misattributed --write  # apply and log
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from scripts.author_identity import printed_name_fits, words
from scripts.fetch_enrichment import derive_research_areas

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
EXTENDED_SOURCE = "openalex"


def _clean_area(name: str) -> str:
    """Directory expertise was scraped from Word-pasted text: a bullet from
    the Symbol font survives as "" (or as the mojibake "ï‚·")."""
    try:
        name = name.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    name = name.replace("", " ")
    return re.sub(r"\s+", " ", name).strip(" -•·")


def find_unlinks(researchers: list[dict], publications: list[dict]) -> list[dict]:
    profile = {
        r["researcher_id"]: r["full_name"]
        for r in researchers
        if r.get("source") != EXTENDED_SOURCE
    }
    out = []
    for p in publications:
        for a in p.get("authors", []):
            rid = a.get("researcher_id")
            if rid not in profile:
                continue
            printed = a.get("full_name", "")
            if words(printed) == words(profile[rid]):
                continue
            if not printed_name_fits(printed, profile[rid]):
                out.append({
                    "publication_id": p["publication_id"],
                    "printed_name": printed,
                    "was_linked_to_id": rid,
                    "was_linked_to_name": profile[rid],
                })
    return out


def apply_unlinks(
    researchers: list[dict],
    publications: list[dict],
    topics: list[dict],
    unlinks: list[dict],
) -> set[int]:
    """Apply in place; return the ids of profiles whose papers changed."""
    drop = {(u["publication_id"], u["was_linked_to_id"], u["printed_name"]) for u in unlinks}
    for p in publications:
        for a in p.get("authors", []):
            if (p["publication_id"], a.get("researcher_id"), a.get("full_name")) in drop:
                a["researcher_id"] = None
    changed = {u["was_linked_to_id"] for u in unlinks}
    before_areas = {
        n
        for r in researchers
        if r["researcher_id"] in changed
        for n in (r.get("research_areas") or [])
    }

    pubs_of: dict[int, list[dict]] = defaultdict(list)
    for p in publications:
        for rid in {a.get("researcher_id") for a in p.get("authors", [])} - {None}:
            pubs_of[rid].append(p)

    topic_id = {t["topic_name"]: t["topic_id"] for t in topics}
    for r in researchers:
        if r.get("source") == EXTENDED_SOURCE:
            continue
        mine = pubs_of[r["researcher_id"]]
        r["publication_count"] = len(mine)
        r["citation_count"] = sum(p.get("citation_count") or 0 for p in mine)
        if r["researcher_id"] not in changed:
            continue
        r["research_areas"] = [
            n for n in (_clean_area(x) for x in derive_research_areas(r, mine)) if n
        ]
        for name in r["research_areas"]:
            if name not in topic_id:
                topic_id[name] = max(topic_id.values(), default=0) + 1
                topics.append({
                    "topic_id": topic_id[name], "topic_name": name, "icon": "sparkles",
                    "description": f"Research and expertise in {name}.",
                    "source": "derived", "researcher_count": 0, "publication_count": 0,
                })
        r["topics"] = [{"topic_id": topic_id[n], "topic_name": n} for n in r["research_areas"]]
        partners: list[dict] = []
        for p in mine:
            for inst in p.get("coauthor_institutions", []):
                code = inst.get("country")
                if code and code != "PK":
                    entry = {"institution": inst["name"], "country": code}
                    if entry not in partners:
                        partners.append(entry)
        r["international_collaborations"] = partners

    # Only the areas those profiles moved between change their head count.
    # (Paper counts per area do not change: unlinking an author leaves the
    # paper and its areas as they were.)
    touched = {
        n
        for r in researchers
        if r["researcher_id"] in changed
        for n in (r.get("research_areas") or [])
    } | before_areas
    directory = [r for r in researchers if r.get("source") != EXTENDED_SOURCE]
    for t in topics:
        if t["topic_name"] in touched:
            t["researcher_count"] = sum(
                1 for r in directory if t["topic_name"] in (r.get("research_areas") or [])
            )
    return changed


def main(write: bool) -> None:
    load = lambda n: json.loads((DATA_DIR / f"{n}.json").read_text("utf-8"))  # noqa: E731
    researchers, publications, topics = load("researchers"), load("publications"), load("topics")
    unlinks = find_unlinks(researchers, publications)
    people = {u["was_linked_to_name"] for u in unlinks}
    print(f"{len(unlinks)} link(s) to remove across {len(people)} profile(s)")
    if not write:
        for u in unlinks[:40]:
            print(f"  {u['printed_name']!r:40} was on {u['was_linked_to_name']!r}")
        return
    apply_unlinks(researchers, publications, topics, unlinks)
    dump = lambda rows: json.dumps(rows, ensure_ascii=False, indent=2)  # noqa: E731
    for name, rows in (("researchers", researchers), ("publications", publications),
                       ("topics", topics)):
        (DATA_DIR / f"{name}.json").write_text(dump(rows), "utf-8")
    log = DATA_DIR / "author_unlinks.json"
    done = json.loads(log.read_text("utf-8")) if log.exists() else []
    log.write_text(dump(done + unlinks), "utf-8")


if __name__ == "__main__":
    main("--write" in sys.argv)
