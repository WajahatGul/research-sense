"""Fold publication-only author records into the faculty member they belong to.

OpenAlex sometimes splits one person across several author IDs when the name
was printed differently on a paper ("Arif ur" on one, "Arif Ur Rahman" on the
rest). The expansion step turned each of those IDs into its own profile, so a
search for "arif" showed the same person twice and one of their papers sat on
a stub nobody would recognise.

A name that merely looks similar is not proof: Pakistan has many people called
Muhammad Sohail. A stub is folded into a faculty profile only when ALL of these
hold, and every merge is written to ``author_merges.json`` with its evidence:

* the stub's name has at least two words and fits exactly one faculty name
  (same first name; the remaining words appear in order, as the full word, a
  transliteration such as Rehman/Rahman, an initial, or a cut-off prefix);
* the two share at least one co-author, on the stub's papers and the
  faculty member's papers;
* the work is on the same subject: a shared topic label, or a word that is
  rare in the corpus appearing in both sets of titles ("preservation");
* they never appear as separate authors on the same paper.

Anything that fails a test is left alone. Idempotent: a second run finds
nothing new to merge.

    python -m scripts.merge_author_variants          # dry run: print candidates
    python -m scripts.merge_author_variants --write  # apply and log
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
EXTENDED_SOURCE = "openalex"  # mirrors app.repositories.loader.EXTENDED_SOURCE

# Spellings of the same name in romanised Urdu/Arabic.
_SAME = {
    "rehman": "rahman", "rahmaan": "rahman",
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad",
    "mohamed": "muhammad", "mohd": "muhammad",
    "ahmed": "ahmad", "hussain": "husain", "hussein": "husain",
}


def name_tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z]+", name.lower())
    return [_SAME.get(w, w) for w in words]


def _word_fits(short: str, full: str) -> bool:
    """"m" fits "muhammad" (initial), "ur" fits "ur", "rah" fits "rahman"."""
    if short == full:
        return True
    return full.startswith(short) and (len(short) == 1 or len(short) >= 3)


def name_fits(stub: str, faculty: str) -> bool:
    """Could ``stub`` be a shortened way of writing ``faculty``?"""
    s, f = name_tokens(stub), name_tokens(faculty)
    if len(s) < 2 or not f or len(s) > len(f):
        return False
    if s[0] != f[0] and not (len(s[0]) == 1 and f[0].startswith(s[0])):
        return False
    i = 1
    for word in s[1:]:
        while i < len(f) and not _word_fits(word, f[i]):
            i += 1
        if i == len(f):
            return False
        i += 1
    return True


def find_merges(researchers: list[dict], publications: list[dict]) -> list[dict]:
    """Return one entry per stub that passes every test in the module docstring."""
    faculty = [r for r in researchers if r.get("source") != EXTENDED_SOURCE]
    stubs = [r for r in researchers if r.get("source") == EXTENDED_SOURCE]

    # Evidence is taken only from papers where the printed author name fits
    # the profile. Some papers are linked to a profile under a different name
    # (an HR professor credited on "Syed Toqeer Haider"'s power-systems work),
    # and borrowing their co-authors would repeat that mistake.
    names = {r["researcher_id"]: r["full_name"] for r in researchers}
    papers_of: dict[int, list[dict]] = defaultdict(list)
    for p in publications:
        for a in p.get("authors", []):
            rid = a.get("researcher_id")
            if rid is None or rid not in names:
                continue
            printed, own = a.get("full_name", ""), names[rid]
            if name_tokens(printed) == name_tokens(own) or name_fits(printed, own):
                papers_of[rid].append(p)

    def coauthors(rid: int) -> set[int]:
        return {
            a["researcher_id"]
            for p in papers_of[rid]
            for a in p.get("authors", [])
            if a.get("researcher_id") not in (None, rid)
        }

    def subjects(rid: int) -> set[str]:
        return {t for p in papers_of[rid] for t in p.get("topic_names", [])}

    # A title word used by under 1% of papers says what the work is about;
    # "analysis" or "model" says nothing.
    title_words = [set(re.findall(r"[a-z]{6,}", p.get("title", "").lower()))
                   for p in publications]
    df: dict[str, int] = defaultdict(int)
    for words in title_words:
        for w in words:
            df[w] += 1
    rare_limit = max(2, len(publications) // 100)

    def rare_words(rid: int) -> set[str]:
        return {
            w
            for p in papers_of[rid]
            for w in re.findall(r"[a-z]{6,}", p.get("title", "").lower())
            if df[w] <= rare_limit
        }

    merges = []
    for stub in stubs:
        fits = [f for f in faculty if name_fits(stub["full_name"], f["full_name"])]
        if len(fits) != 1:
            continue
        person = fits[0]
        sid, fid = stub["researcher_id"], person["researcher_id"]
        mine = coauthors(sid)
        if fid in mine:  # both on one paper: two different people
            continue
        shared = mine & coauthors(fid)
        if not shared:
            continue
        same_subject = sorted(subjects(sid) & subjects(fid)) or sorted(
            rare_words(sid) & rare_words(fid)
        )
        if not same_subject:
            continue
        merges.append({
            "stub_id": sid,
            "stub_name": stub["full_name"],
            "stub_openalex_id": stub.get("openalex_id"),
            "into_id": fid,
            "into_name": person["full_name"],
            "shared_coauthors": sorted(names[c] for c in shared),
            "shared_subject": same_subject[:5],
            "publication_ids": sorted(p["publication_id"] for p in papers_of[sid]),
        })
    return merges


def apply_merges(
    researchers: list[dict], publications: list[dict], merges: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Move each stub's authorships to the faculty record and drop the stub."""
    into = {m["stub_id"]: m["into_id"] for m in merges}
    by_id = {r["researcher_id"]: r for r in researchers}
    for p in publications:
        for a in p.get("authors", []):
            target = into.get(a.get("researcher_id"))
            if target is not None:
                a["researcher_id"] = target
                a["full_name"] = by_id[target]["full_name"]
    for m in merges:
        person = by_id[m["into_id"]]
        stub = by_id[m["stub_id"]]
        person["publication_count"] = (person.get("publication_count") or 0) + len(
            m["publication_ids"]
        )
        person["citation_count"] = (person.get("citation_count") or 0) + (
            stub.get("citation_count") or 0
        )
        also = person.setdefault("also_published_as", [])
        also.append({"name": m["stub_name"], "openalex_id": m["stub_openalex_id"]})
    kept = [r for r in researchers if r["researcher_id"] not in into]
    return kept, publications


def main(write: bool) -> None:
    researchers = json.loads((DATA_DIR / "researchers.json").read_text("utf-8"))
    publications = json.loads((DATA_DIR / "publications.json").read_text("utf-8"))
    merges = find_merges(researchers, publications)
    for m in merges:
        print(f"  {m['stub_name']!r:32} -> {m['into_name']!r:32} "
              f"shared: {', '.join(m['shared_coauthors'])}")
    print(f"{len(merges)} merge(s)")
    if not write or not merges:
        return
    researchers, publications = apply_merges(researchers, publications, merges)
    dump = lambda rows: json.dumps(rows, ensure_ascii=False, indent=2)  # noqa: E731
    (DATA_DIR / "researchers.json").write_text(dump(researchers), "utf-8")
    (DATA_DIR / "publications.json").write_text(dump(publications), "utf-8")
    log = DATA_DIR / "author_merges.json"
    done = json.loads(log.read_text("utf-8")) if log.exists() else []
    log.write_text(dump(done + merges), "utf-8")


if __name__ == "__main__":
    main("--write" in sys.argv)
