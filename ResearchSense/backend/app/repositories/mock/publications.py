"""JSON-backed PublicationRepository implementation."""

from __future__ import annotations

import re
from datetime import date as _date

from app.repositories import loader
from app.repositories.base import PublicationRepository
from app.schemas.publication import Publication

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
        result = []
        for p in rows:
            if query and query.lower() not in p["title"].lower():
                continue
            if year is not None and p["publication_year"] != year:
                continue
            if campus and p.get("campus") != campus:
                continue
            if topic_id is not None and topic_id not in {
                t["topic_id"] for t in p.get("topics", [])
            }:
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
            result.append(Publication(**p))
        result.sort(key=lambda p: p.publication_year, reverse=True)
        return result

    def get(self, publication_id: int) -> Publication | None:
        rec = next(
            (p for p in self._all() if p["publication_id"] == publication_id), None
        )
        return Publication(**rec) if rec else None
