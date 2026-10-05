"""One work, one record: fold copies of the same paper together.

The same work reaches the corpus more than once: a journal article and its
preprint on SSRN, Preprints.org or Research Square; Zenodo's two DOIs for one
upload (the "concept" and the "version"); a journal article reprinted as a
book chapter; a journal that re-issued the article under a new DOI. Each copy
showed as its own paper, so an author's list repeated itself and their paper
count was inflated.

Two records are the same work when their titles match (ignoring case,
spacing and punctuation) and they share an author. One record is kept, in
this order of preference: a journal or book rather than a preprint server,
one with a DOI, the most cited, the earliest added. The others become its
``versions`` (still listed on the paper's page, since a preprint is often
the free copy), their author links carry over, and their ids resolve to the
kept record through ``publication_duplicates.json`` so old links still work.

Idempotent: a second run finds nothing to merge.

    python -m scripts.merge_duplicate_publications          # dry run
    python -m scripts.merge_duplicate_publications --write  # apply and log
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
EXTENDED_SOURCE = "openalex"
_MIN_TITLE = 16  # "Introduction" or an empty title is not an identity

_REPOSITORY = re.compile(
    r"zenodo|ssrn|preprint|research square|figshare|arxiv|biorxiv|medrxiv|"
    r"techrxiv|\bosf\b|unindexed|repository|e-?prints|ebooks",
    re.I,
)


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _authors(p: dict) -> set[str]:
    return {
        re.sub(r"[^a-z]", "", a.get("full_name", "").lower())
        for a in p.get("authors", [])
    }


def _preference(p: dict) -> tuple:
    return (
        bool(_REPOSITORY.search(p.get("journal_name") or "")),  # False sorts first
        not p.get("doi"),
        -(p.get("citation_count") or 0),
        p["publication_id"],
    )


def find_duplicates(publications: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in publications:
        key = title_key(p.get("title", ""))
        if len(key) >= _MIN_TITLE:
            groups[key].append(p)
    merges = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=_preference)
        keep = rows[0]
        for other in rows[1:]:
            if not _authors(keep) & _authors(other):
                continue  # same title, different people: not the same work
            merges.append(
                {
                    "removed_id": other["publication_id"],
                    "kept_id": keep["publication_id"],
                    "title": other["title"],
                    "journal_name": other.get("journal_name") or "",
                    "doi": other.get("doi"),
                    "publication_year": other.get("publication_year"),
                }
            )
    return merges


def apply_merges(
    researchers: list[dict],
    publications: list[dict],
    topics: list[dict],
    merges: list[dict],
) -> list[dict]:
    by_id = {p["publication_id"]: p for p in publications}
    removed = {m["removed_id"] for m in merges}
    touched_people: set[int] = set()
    for m in merges:
        keep, other = by_id[m["kept_id"]], by_id[m["removed_id"]]
        keep.setdefault("versions", []).append(
            {
                "journal_name": m["journal_name"],
                "doi": m["doi"],
                "publication_year": m["publication_year"],
            }
        )
        keep["citation_count"] = max(
            keep.get("citation_count") or 0, other.get("citation_count") or 0
        )
        # A link made on the copy (and missing on the kept record) carries over.
        linked = {a.get("researcher_id") for a in keep["authors"]} - {None}
        for a in other.get("authors", []):
            rid = a.get("researcher_id")
            touched_people.add(rid)
            if rid is None or rid in linked:
                continue
            name = re.sub(r"[^a-z]", "", a.get("full_name", "").lower())
            for k in keep["authors"]:
                if (
                    k.get("researcher_id") is None
                    and re.sub(r"[^a-z]", "", k.get("full_name", "").lower()) == name
                ):
                    k["researcher_id"] = rid
                    linked.add(rid)
                    break
    kept = [p for p in publications if p["publication_id"] not in removed]

    # Counts follow the records that remain.
    pubs_of: dict[int, list[dict]] = defaultdict(list)
    for p in kept:
        for rid in {a.get("researcher_id") for a in p.get("authors", [])} - {None}:
            pubs_of[rid].append(p)
    for r in researchers:
        rid = r["researcher_id"]
        if r.get("source") == EXTENDED_SOURCE and rid not in touched_people:
            continue
        r["publication_count"] = len(pubs_of[rid])
        r["citation_count"] = sum(p.get("citation_count") or 0 for p in pubs_of[rid])
    per_topic = Counter(t["topic_id"] for p in kept for t in p.get("topics", []))
    for t in topics:
        t["publication_count"] = per_topic[t["topic_id"]]
    return kept


def main(write: bool) -> None:
    load = lambda n: json.loads((DATA_DIR / f"{n}.json").read_text("utf-8"))  # noqa: E731
    researchers, publications, topics = (
        load("researchers"),
        load("publications"),
        load("topics"),
    )
    merges = find_duplicates(publications)
    print(
        f"{len(merges)} duplicate record(s) to fold into"
        f" {len({m['kept_id'] for m in merges})}"
    )
    if not write:
        for m in merges[:30]:
            print(
                f"  {m['removed_id']:>5} -> {m['kept_id']:<5}"
                f" {m['journal_name'][:30]!r:32} {m['title'][:50]}"
            )
        return
    publications = apply_merges(researchers, publications, topics, merges)
    dump = lambda rows: json.dumps(rows, ensure_ascii=False, indent=2)  # noqa: E731
    for name, rows in (
        ("researchers", researchers),
        ("publications", publications),
        ("topics", topics),
    ):
        (DATA_DIR / f"{name}.json").write_text(dump(rows), "utf-8")
    log = DATA_DIR / "publication_duplicates.json"
    done = json.loads(log.read_text("utf-8")) if log.exists() else []
    log.write_text(dump(done + merges), "utf-8")


if __name__ == "__main__":
    main("--write" in sys.argv)
