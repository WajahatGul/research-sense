"""Suggestions while someone is still typing.

A search box that shows nothing until Enter makes people guess the spelling
of a name and then wait for a results page to find out they were wrong.
Showing the closest people, areas and papers after two letters turns that
guess into a choice, and a choice is faster than recall.

This reads the same prepared indexes as the full search, so a suggestion is
always something the results page would also find, and a keystroke costs a
scan of pre-tokenised entries rather than building thousands of objects.
"""

from __future__ import annotations

import heapq

from pydantic import BaseModel

from app.core.areas import paper_areas
from app.core.textsearch import Query, index_for
from app.repositories import loader
from app.repositories.mock.publications import _search_fields as _publication_fields
from app.repositories.mock.researchers import _search_fields as _researcher_fields
from app.repositories.mock.topics import _head_counts

SCOPES = ("researchers", "topics", "publications")
MIN_CHARS = 2


class Suggestion(BaseModel):
    kind: str  # "researcher" | "topic" | "publication"
    id: int
    label: str
    detail: str = ""


def _topic_fields(t: dict) -> tuple[str, ...]:
    return (t["topic_name"],)


def _best(
    name: str, rows: list[dict], fields, q: Query, limit: int, tie
) -> list[tuple[float, dict]]:
    entries = index_for(name, rows, fields).entries
    scored = []
    for i, _row in enumerate(rows):
        s = q.score_entry(entries[i])
        if s is not None:
            scored.append((s, i))
    top = heapq.nsmallest(limit, scored, key=lambda si: (-si[0], tie(rows[si[1]])))
    return [(s, rows[i]) for s, i in top]


# Mixed suggestions are ranked by how well each one matches, not grouped by
# kind: typing "machine" used to list three people first (they match only
# through their research areas) and the area "Machine Learning" fourth. On
# an equal match an area comes first (the broadest destination), then a
# person, then a single paper.
_KIND_ORDER = {"topic": 0, "researcher": 1, "publication": 2}
PER_KIND_IN_MIX = 5
LEAD_KIND_CAP = 5
OTHER_KIND_CAP = 3
GUARANTEED_PER_KIND = 2
EMPTY_AREA_PENALTY = 50


def suggest(
    text: str | None, scope: str | None = None, limit: int = 5
) -> list[Suggestion]:
    """Suggestions for ``text``. With a scope, up to ``limit`` of that kind;
    without one, the best ``limit`` across all kinds."""
    q = Query(text)
    if len(q.text) < MIN_CHARS or not q:
        return []
    mixed = scope not in SCOPES
    scopes = list(SCOPES) if mixed else [scope]
    per_kind = min(limit, PER_KIND_IN_MIX) if mixed else limit
    ranked: list[tuple[float, Suggestion]] = []

    if "researchers" in scopes:
        rows = loader.load("researchers")
        # Full directory profiles before name-only authors, then the more
        # published person: the same tie-break the results page uses.
        for score, r in _best(
            "researchers",
            rows,
            _researcher_fields,
            q,
            per_kind,
            lambda r: (loader.is_extended(r), -(r.get("publication_count") or 0)),
        ):
            detail = " · ".join(
                x for x in (r.get("designation"), r.get("department")) if x
            )
            ranked.append(
                (
                    score,
                    Suggestion(
                        kind="researcher",
                        id=r["researcher_id"],
                        label=r["full_name"],
                        detail=detail or "Author on indexed papers",
                    ),
                )
            )

    if "topics" in scopes:
        rows = loader.load("topics")
        papers = paper_areas(rows, loader.load("publications"))[1]
        people = _head_counts(rows, loader.load("researchers"))
        for score, t in _best(
            "topics",
            rows,
            _topic_fields,
            q,
            per_kind + 3,
            lambda t: -papers.get(t["topic_id"], 0),
        ):
            n = papers.get(t["topic_id"], 0)
            m = people.get(" ".join(t["topic_name"].lower().split()), 0)
            if n == 0:
                # An area with no papers (someone's own wording for their
                # expertise) is a weak destination: keep it below every
                # area that has papers matching as well.
                score -= EMPTY_AREA_PENALTY
            detail = " · ".join(
                x
                for x in (
                    f"{n} publication{'' if n == 1 else 's'}" if n else "",
                    f"{m} researcher{'' if m == 1 else 's'}" if m else "",
                )
                if x
            )
            ranked.append(
                (
                    score,
                    Suggestion(
                        kind="topic",
                        id=t["topic_id"],
                        label=t["topic_name"],
                        detail=detail or "No papers yet",
                    ),
                )
            )

    if "publications" in scopes:
        rows = loader.load("publications")
        for score, p in _best(
            "publications",
            rows,
            _publication_fields,
            q,
            per_kind,
            lambda p: -(p.get("publication_year") or 0),
        ):
            detail = " · ".join(
                str(x) for x in (p.get("publication_year"), p.get("journal_name")) if x
            )
            ranked.append(
                (
                    score,
                    Suggestion(
                        kind="publication",
                        id=p["publication_id"],
                        label=p["title"],
                        detail=detail,
                    ),
                )
            )

    if not mixed:
        return [s for _, s in ranked]
    # sorted() is stable, so within a kind the order chosen above is kept.
    ranked.sort(key=lambda sr: (-sr[0], _KIND_ORDER[sr[1].kind]))
    # Keep some variety. Every kind that matched is guaranteed a couple of
    # places, so "machine learning" still offers the people who work on it;
    # the rest go by relevance, and the kind that matches best (people, for
    # a name) may fill most of the list.
    lead = ranked[0][1].kind if ranked else None
    by_kind: dict[str, list[int]] = {}
    for i, (_, sug) in enumerate(ranked):
        by_kind.setdefault(sug.kind, []).append(i)
    chosen = {i for idxs in by_kind.values() for i in idxs[:GUARANTEED_PER_KIND]}
    count = {k: min(len(v), GUARANTEED_PER_KIND) for k, v in by_kind.items()}
    for i, (_, sug) in enumerate(ranked):
        if len(chosen) >= limit:
            break
        cap = LEAD_KIND_CAP if sug.kind == lead else OTHER_KIND_CAP
        if i not in chosen and count[sug.kind] < cap:
            chosen.add(i)
            count[sug.kind] += 1
    picked = sorted(chosen)[:limit] if len(chosen) > limit else sorted(chosen)
    return [ranked[i][1] for i in picked]
