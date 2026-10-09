"""Departments (an organisation's units) as a place to browse from."""

from __future__ import annotations

import re
from collections import Counter

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.repositories import loader

router = APIRouter(prefix="/api/departments", tags=["departments"])

TOP_AREAS = 3


class DepartmentSummary(BaseModel):
    name: str
    researchers: int
    publications: int
    campuses: list[str]
    top_areas: list[str]


@router.get("", response_model=list[DepartmentSummary])
def list_departments():
    """Each unit with its people, its papers and what it mostly works on.

    The home page's "22 Departments" used to open Analytics, where the
    departments are one bar chart among many: a count with nowhere to go.
    """
    people = [
        r
        for r in loader.load("researchers")
        if not loader.is_extended(r) and (r.get("department") or "").strip()
    ]
    dept_of = {r["researcher_id"]: r["department"] for r in people}
    papers: dict[str, set[int]] = {}
    for p in loader.load("publications"):
        for a in p.get("authors", []):
            d = dept_of.get(a.get("researcher_id"))
            if d:
                papers.setdefault(d, set()).add(p["publication_id"])

    out = []
    for name in sorted({r["department"] for r in people}):
        members = [r for r in people if r["department"] == name]
        areas = Counter(a for r in members for a in (r.get("research_areas") or []))
        out.append(
            DepartmentSummary(
                name=name,
                researchers=len(members),
                publications=len(papers.get(name, ())),
                campuses=sorted({r.get("campus") or "" for r in members} - {""}),
                top_areas=[a for a, _ in areas.most_common(TOP_AREAS)],
            )
        )
    # Largest first: the order people scan a list of units in.
    out.sort(key=lambda d: (-d.researchers, d.name))
    return out


@router.get("/{name}/report")
def annual_report(name: str, year: int = Query(ge=1950, le=2100)):
    """The department's research output for one year, as an Excel workbook."""
    from app.services import export_service

    try:
        body = export_service.department_report(name, year)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}-research-{year}.xlsx"'
        },
    )
