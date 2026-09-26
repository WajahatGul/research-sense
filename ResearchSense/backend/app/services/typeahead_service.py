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

from app.core.textsearch import Query, index_for
from app.repositories import loader
from app.repositories.mock.publications import _search_fields as _publication_fields
from app.repositories.mock.researchers import _search_fields as _researcher_fields

SCOPES = ("researchers", "topics", "publications")
MIN_CHARS = 2


class Suggestion(BaseModel):
    kind: str  # "researcher" | "topic" | "publication"
    id: int
    label: str
    detail: str = ""


def _topic_fields(t: dict) -> tuple[str, ...]:
    return (t["topic_name"],)


def _best(name: str, rows: list[dict], fields, q: Query, limit: int, tie) -> list[dict]:
    entries = index_for(name, rows, fields).entries
    scored = []
    for i, row in enumerate(rows):
        s = q.score_entry(entries[i])
        if s is not None:
            scored.append((s, i))
    top = heapq.nsmallest(limit, scored, key=lambda si: (-si[0], tie(rows[si[1]])))
    return [rows[i] for _, i in top]


def suggest(text: str | None, scope: str | None = None, limit: int = 5) -> list[Suggestion]:
    q = Query(text)
    if len(q.text) < MIN_CHARS or not q:
        return []
    scopes = [scope] if scope in SCOPES else list(SCOPES)
    out: list[Suggestion] = []

    if "researchers" in scopes:
        rows = loader.load("researchers")
        # Full directory profiles before name-only authors, then the more
        # published person: the same tie-break the results page uses.
        for r in _best("researchers", rows, _researcher_fields, q, limit,
                       lambda r: (loader.is_extended(r), -(r.get("publication_count") or 0))):
            detail = " · ".join(x for x in (r.get("designation"), r.get("department")) if x)
            out.append(Suggestion(kind="researcher", id=r["researcher_id"],
                                  label=r["full_name"],
                                  detail=detail or "Author on indexed papers"))

    if "topics" in scopes:
        rows = loader.load("topics")
        for t in _best("topics", rows, _topic_fields, q, limit,
                       lambda t: -(t.get("publication_count") or 0)):
            n = t.get("publication_count") or 0
            out.append(Suggestion(kind="topic", id=t["topic_id"], label=t["topic_name"],
                                  detail=f"{n} publication{'' if n == 1 else 's'}"))

    if "publications" in scopes:
        rows = loader.load("publications")
        for p in _best("publications", rows, _publication_fields, q, limit,
                       lambda p: -(p.get("publication_year") or 0)):
            detail = " · ".join(
                str(x) for x in (p.get("publication_year"), p.get("journal_name")) if x
            )
            out.append(Suggestion(kind="publication", id=p["publication_id"],
                                  label=p["title"], detail=detail))
    return out
