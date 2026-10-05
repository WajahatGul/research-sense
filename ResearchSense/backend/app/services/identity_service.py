"""Human decisions about who wrote what, kept for good.

The automatic clean-ups (scripts/merge_author_variants.py,
scripts/unlink_misattributed.py) decide what the evidence settles. The rest
needs a person: "this paper is not mine", "this author record is also me",
"these two are different people". This module holds those decisions.

A decision names things by what survives a data refresh: a paper by its DOI
(or its normalised title when it has none), a person by their directory id
or their OpenAlex author id, never by the paper numbers the fetch step
reassigns. Approved decisions live in ``identity_decisions.json`` and are
applied again after every refresh, after the automatic passes, so a
person's word outranks a heuristic and is never silently undone.

Researchers propose (their proposals wait for an administrator in the
``corrections`` table); administrators decide. "No, that is not me" about a
suggested record is recorded at once: it only stops a suggestion, and it
changes no data.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.repositories import loader
from app.repositories.accounts import AccountStore

DECISIONS = "identity_decisions"


def _data_dir() -> Path:
    return loader.workspace_dir(loader.current_workspace())


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def paper_key(p: dict) -> dict:
    """What identifies a paper across refreshes."""
    doi = (p.get("doi") or "").strip().lower() or None
    return {
        "doi": doi,
        "title_key": title_key(p.get("title", "")),
        "title": p.get("title", ""),
    }


def _find_papers(publications: list[dict], key: dict) -> list[dict]:
    if key.get("doi"):
        hits = [
            p
            for p in publications
            if (p.get("doi") or "").strip().lower() == key["doi"]
        ]
        if hits:
            return hits
    return [
        p for p in publications if title_key(p.get("title", "")) == key.get("title_key")
    ]


# --- the durable record -------------------------------------------------------


def decisions() -> list[dict]:
    path = _data_dir() / f"{DECISIONS}.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else []


def _record(decision: dict) -> dict:
    decision = {"id": uuid.uuid4().hex[:12], "decided_at": _now(), **decision}
    path = _data_dir() / f"{DECISIONS}.json"
    rows = decisions()
    rows.append(decision)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
    return decision


# --- applying decisions to the data ------------------------------------------


def apply_all(
    researchers: list[dict],
    publications: list[dict],
    topics: list[dict],
    rows: list[dict] | None = None,
) -> tuple[list[dict], set[int]]:
    """Apply decisions in place; return (researchers, changed profile ids).

    Researchers may shrink (a merged author record disappears), so the list
    is returned rather than only mutated.
    """
    from scripts.merge_author_variants import apply_merges
    from scripts.unlink_misattributed import apply_unlinks

    rows = decisions() if rows is None else rows
    unlinks, merges = [], []
    by_openalex = {r.get("openalex_id"): r for r in researchers if r.get("openalex_id")}
    ids = {r["researcher_id"] for r in researchers}
    for d in rows:
        if d["type"] == "not_author" and d["profile"]["researcher_id"] in ids:
            rid = d["profile"]["researcher_id"]
            for p in _find_papers(publications, d["paper"]):
                for a in p.get("authors", []):
                    if a.get("researcher_id") == rid:
                        unlinks.append(
                            {
                                "publication_id": p["publication_id"],
                                "printed_name": a.get("full_name"),
                                "was_linked_to_id": rid,
                                "was_linked_to_name": d["profile"]["name"],
                            }
                        )
        elif d["type"] == "same_person":
            stub = by_openalex.get(d["other"]["openalex_id"])
            into = d["profile"]["researcher_id"]
            if stub is None or stub["researcher_id"] == into or into not in ids:
                continue  # already merged, or the record no longer exists
            if stub.get("source") != loader.EXTENDED_SOURCE:
                continue  # never fold one directory profile into another
            merges.append(
                {
                    "stub_id": stub["researcher_id"],
                    "stub_name": stub["full_name"],
                    "stub_openalex_id": stub.get("openalex_id"),
                    "into_id": into,
                    "publication_ids": [
                        p["publication_id"]
                        for p in publications
                        if any(
                            a.get("researcher_id") == stub["researcher_id"]
                            for a in p.get("authors", [])
                        )
                    ],
                }
            )
    changed: set[int] = set()
    if merges:
        researchers, publications = apply_merges(researchers, publications, merges)
        changed |= {m["into_id"] for m in merges}
    if unlinks:
        changed |= apply_unlinks(researchers, publications, topics, unlinks)
    return researchers, changed


def apply_and_save(rows: list[dict] | None = None) -> set[int]:
    """Apply decisions to the stored data and refresh every cached view."""
    base = _data_dir()
    load = lambda n: json.loads((base / f"{n}.json").read_text("utf-8"))  # noqa: E731
    researchers, publications, topics = (
        load("researchers"),
        load("publications"),
        load("topics"),
    )
    researchers, changed = apply_all(researchers, publications, topics, rows)
    if changed:
        dump = lambda rows: json.dumps(rows, ensure_ascii=False, indent=2)  # noqa: E731
        for name, data in (
            ("researchers", researchers),
            ("publications", publications),
            ("topics", topics),
        ):
            (base / f"{name}.json").write_text(dump(data), "utf-8")
        loader.clear_cache()
        from app.services.rag import authored

        authored._Store.reset()
    return changed


# --- suggestions: author records that may be the same person -----------------

_candidate_cache: dict[tuple[int, int], list[dict]] = {}


def candidates(
    for_researcher: int | None = None, limit: int = 50, include_waiting: bool = False
) -> list[dict]:
    """Publication-only author records whose name fits a directory profile,
    that no automatic rule or human has settled yet, strongest evidence first.
    """
    from scripts.author_identity import printed_name_fits, words

    researchers = loader.load("researchers")
    publications = loader.load("publications")
    key = (id(researchers), id(publications))
    if key not in _candidate_cache:
        directory = [r for r in researchers if not loader.is_extended(r)]
        stubs = [r for r in researchers if loader.is_extended(r)]
        by_letter: dict[str, list[dict]] = defaultdict(list)
        for r in directory:
            w = words(r["full_name"])
            if w:
                by_letter[w[0][0]].append(r)
        papers_of: dict[int, list[dict]] = defaultdict(list)
        for p in publications:
            for rid in {a.get("researcher_id") for a in p.get("authors", [])} - {None}:
                papers_of[rid].append(p)

        seen_people: dict[int, set[int]] = {}
        seen_areas: dict[int, set[str]] = {}

        def coauthors(rid: int) -> set[int]:
            if rid not in seen_people:
                seen_people[rid] = {
                    a["researcher_id"]
                    for p in papers_of[rid]
                    for a in p["authors"]
                    if a.get("researcher_id") not in (None, rid)
                }
            return seen_people[rid]

        def areas(rid: int) -> set[str]:
            if rid not in seen_areas:
                seen_areas[rid] = {
                    t for p in papers_of[rid] for t in p.get("topic_names", [])
                }
            return seen_areas[rid]

        out = []
        for s in stubs:
            w = words(s["full_name"])
            if len(w) < 2:
                continue
            for r in by_letter.get(w[0][0], []):
                if not printed_name_fits(s["full_name"], r["full_name"]):
                    continue
                shared_people = coauthors(s["researcher_id"]) & coauthors(
                    r["researcher_id"]
                )
                shared_areas = areas(s["researcher_id"]) & areas(r["researcher_id"])
                out.append(
                    {
                        "researcher_id": r["researcher_id"],
                        "profile_name": r["full_name"],
                        "openalex_id": s.get("openalex_id"),
                        "other_name": s["full_name"],
                        "papers": [
                            {
                                "publication_id": p["publication_id"],
                                "title": p["title"],
                                "year": p.get("publication_year"),
                            }
                            for p in papers_of[s["researcher_id"]][:3]
                        ],
                        "paper_count": len(papers_of[s["researcher_id"]]),
                        "shared_coauthors": len(shared_people),
                        "shared_areas": sorted(shared_areas)[:3],
                        "score": 3 * len(shared_people) + len(shared_areas),
                    }
                )
        out.sort(key=lambda c: (-c["score"], c["profile_name"]))
        _candidate_cache.clear()
        _candidate_cache[key] = out

    settled = {
        (d["profile"]["researcher_id"], d["other"]["openalex_id"])
        for d in decisions()
        if d["type"] in ("same_person", "different_people")
    }
    waiting = (
        set()
        if include_waiting
        else {
            (c["researcher_id"], json.loads(c["payload_json"])["other"]["openalex_id"])
            for c in AccountStore.instance().pending_corrections()
            if c["kind"] == "same_person"
        }
    )
    rows = [
        c
        for c in _candidate_cache[key]
        if (c["researcher_id"], c["openalex_id"]) not in settled | waiting
        and (for_researcher is None or c["researcher_id"] == for_researcher)
    ]
    return rows[:limit]


# --- proposals and decisions ---------------------------------------------------


def _profile(researcher_id: int) -> dict:
    r = next(
        (x for x in loader.load("researchers") if x["researcher_id"] == researcher_id),
        None,
    )
    if r is None:
        raise LookupError("No such researcher")
    return {
        "researcher_id": researcher_id,
        "name": r["full_name"],
        "orcid_id": r.get("orcid_id"),
        "openalex_id": r.get("openalex_id"),
    }


def propose_not_author(researcher_id: int, publication_id: int, note: str) -> int:
    paper = next(
        (
            p
            for p in loader.load("publications")
            if p["publication_id"] == publication_id
        ),
        None,
    )
    if paper is None or not any(
        a.get("researcher_id") == researcher_id for a in paper["authors"]
    ):
        raise LookupError("That paper is not on your profile")
    payload = {"profile": _profile(researcher_id), "paper": paper_key(paper)}
    return AccountStore.instance().create_correction(
        "not_author", researcher_id, json.dumps(payload), note, "researcher"
    )


def propose_same_person(researcher_id: int, openalex_id: str, note: str) -> int:
    other = next(
        (
            r
            for r in loader.load("researchers")
            if r.get("openalex_id") == openalex_id and loader.is_extended(r)
        ),
        None,
    )
    if other is None:
        raise LookupError("No such author record")
    payload = {
        "profile": _profile(researcher_id),
        "other": {"openalex_id": openalex_id, "name": other["full_name"]},
    }
    return AccountStore.instance().create_correction(
        "same_person", researcher_id, json.dumps(payload), note, "researcher"
    )


def decide_different_people(researcher_id: int, openalex_id: str, by: str) -> dict:
    other = next(
        (r for r in loader.load("researchers") if r.get("openalex_id") == openalex_id),
        None,
    )
    return _record(
        {
            "type": "different_people",
            "profile": _profile(researcher_id),
            "other": {
                "openalex_id": openalex_id,
                "name": other["full_name"] if other else "",
            },
            "decided_by": by,
        }
    )


def decide_same_person(
    researcher_id: int, openalex_id: str, by: str, note: str = ""
) -> dict:
    other = next(
        (r for r in loader.load("researchers") if r.get("openalex_id") == openalex_id),
        None,
    )
    d = _record(
        {
            "type": "same_person",
            "profile": _profile(researcher_id),
            "other": {
                "openalex_id": openalex_id,
                "name": other["full_name"] if other else "",
            },
            "decided_by": by,
            "note": note,
        }
    )
    apply_and_save([d])
    return d


def approve_correction(correction_id: int) -> dict:
    store = AccountStore.instance()
    c = store.get_correction(correction_id)
    if c is None or c["status"] != "pending":
        raise LookupError("No such pending correction")
    payload = json.loads(c["payload_json"])
    d = _record(
        {
            "type": c["kind"],
            **payload,
            "decided_by": "admin",
            "raised_by": c["raised_by"],
            "note": c.get("note") or "",
        }
    )
    store.set_correction_status(correction_id, "approved")
    apply_and_save([d])
    return d


def reject_correction(correction_id: int, note: str | None) -> None:
    store = AccountStore.instance()
    c = store.get_correction(correction_id)
    if c is None or c["status"] != "pending":
        raise LookupError("No such pending correction")
    store.set_correction_status(correction_id, "rejected", note)
