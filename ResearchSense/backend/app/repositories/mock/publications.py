"""JSON-backed PublicationRepository implementation."""

from __future__ import annotations

import re
from datetime import date as _date

from app.core.areas import paper_areas
from app.core.textsearch import Query, correct, index_for
from app.repositories import loader
from app.repositories.base import PublicationRepository
from app.schemas.publication import Publication

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _search_fields(p: dict) -> tuple[str, ...]:
    """Title first, then the authors and areas people also search by."""
    return (
        p.get("title") or "",
        " ".join(
            a.get("name") or a.get("full_name") or "" for a in p.get("authors", [])
        ),
        " ".join(t.get("topic_name") or "" for t in p.get("topics", [])),
    )


def effective_date(p: dict) -> str:
    """ISO date used for range filtering. Records predating full-date capture
    carry only a year; treat them as Jan 1 so they still sort and filter."""
    date = p.get("publication_date")
    if isinstance(date, str) and _DATE_RE.match(date):
        try:
            _date.fromisoformat(date)
            return date
        except ValueError:
            pass
    year = p.get("publication_year") or 0
    if year:
        return f"{year:04d}-01-01"
    return "0000-01-01"


def publication_matches(
    p: dict,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    department: str | None = None,
    publication_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    dept_of: dict[int, str],
) -> bool:
    """Additive filters: inclusive year range, inclusive date range,
    any-author department, and paper type. None means 'no constraint'."""
    year = p.get("publication_year") or 0
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    if date_from is not None or date_to is not None:
        eff = effective_date(p)
        if date_from is not None and eff < date_from:
            return False
        if date_to is not None and eff > date_to:
            return False
    if publication_type and p.get("publication_type") != publication_type:
        return False
    if department:
        depts = {dept_of.get(a.get("researcher_id")) for a in p.get("authors", [])}
        if department not in depts:
            return False
    return True


class MockPublicationRepository(PublicationRepository):
    def _all(self) -> list[dict]:
        return loader.load("publications")

    def list(
        self,
        *,
        query=None,
        year=None,
        topic_id=None,
        author_id=None,
        campus=None,
        year_from=None,
        year_to=None,
        department=None,
        publication_type=None,
        date_from=None,
        date_to=None,
    ):
        rows = self._all()
        dept_of = {
            r["researcher_id"]: r.get("department") for r in loader.load("researchers")
        }
        q = Query(query)
        entries = index_for("publications", rows, _search_fields).entries if q else None
        in_area = (
            paper_areas(loader.load("topics"), rows)[0] if topic_id is not None else {}
        )
        result: list[tuple[float, Publication]] = []
        for i, p in enumerate(rows):
            score = q.score_entry(entries[i]) if entries else 0.0
            if score is None:
                continue
            if year is not None and p["publication_year"] != year:
                continue
            if campus and p.get("campus") != campus:
                continue
            if topic_id is not None and topic_id not in in_area.get(
                p["publication_id"], ()
            ):
                continue
            if author_id is not None and not any(
                a.get("researcher_id") == author_id for a in p.get("authors", [])
            ):
                continue
            if not publication_matches(
                p,
                year_from=year_from,
                year_to=year_to,
                department=department,
                publication_type=publication_type,
                date_from=date_from,
                date_to=date_to,
                dept_of=dept_of,
            ):
                continue
            result.append((score, Publication(**p)))
        # Best title match first when searching; newest first when browsing.
        result.sort(key=lambda sp: (-sp[0], -(sp[1].publication_year or 0)))
        return [p for _, p in result]

    def suggest(self, query: str | None) -> str | None:
        vocab = index_for("publications", self._all(), _search_fields).vocab
        return correct(query, vocab)

    def get(self, publication_id: int) -> Publication | None:
        rec = next(
            (p for p in self._all() if p["publication_id"] == publication_id), None
        )
        if rec is None:
            # A copy folded into another record (a preprint, a second DOI):
            # old links, bookmarks and chat history still reach the paper.
            kept = next(
                (
                    m["kept_id"]
                    for m in loader.load("publication_duplicates")
                    if m["removed_id"] == publication_id
                ),
                None,
            )
            if kept is not None and kept != publication_id:
                return self.get(kept)
        return Publication(**rec) if rec else None

    def related(self, publication_id: int, limit: int = 5) -> list[Publication]:
        """Papers sharing this one's research areas, then its authors.

        A shared area counts for more than a shared author: a reader who
        opened a paper on fish classification wants more on that subject,
        not the same author's unrelated work. Ties go to the newer paper.
        """
        rows = self._all()
        me = next((p for p in rows if p["publication_id"] == publication_id), None)
        if me is None:
            return []
        areas = set(me.get("topic_names", []))
        people = {
            a["researcher_id"] for a in me.get("authors", []) if a.get("researcher_id")
        }
        title = me["title"].strip().lower()
        scored = []
        for p in rows:
            if (
                p["publication_id"] == publication_id
                or p["title"].strip().lower() == title
            ):
                continue
            shared_areas = len(areas & set(p.get("topic_names", [])))
            shared_people = len(
                people & {a.get("researcher_id") for a in p.get("authors", [])}
            )
            score = 2 * shared_areas + shared_people
            if score:
                scored.append((score, p.get("publication_year") or 0, p))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        return [Publication(**p) for _, _, p in scored[:limit]]
