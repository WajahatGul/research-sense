"""Researcher endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import get_researcher_service
from app.schemas.common import Paginated
from app.schemas.researcher import CollaborationSuggestion, Researcher, ResearcherDetail
from app.services import usage_service
from app.services.researcher_service import ResearcherService

router = APIRouter(prefix="/api/researchers", tags=["researchers"])


@router.get("", response_model=Paginated[Researcher])
def list_researchers(
    q: str | None = None,
    campus: str | None = None,
    department: str | None = None,
    designation: str | None = None,
    topic_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    service: ResearcherService = Depends(get_researcher_service),
):
    result = service.list(
        query=q,
        campus=campus,
        department=department,
        designation=designation,
        topic_id=topic_id,
        page=page,
        page_size=page_size,
    )
    # A search alone that finds nothing is a gap in the directory (filters
    # narrowing to nothing are not).
    if q and result.total == 0 and not (campus or department or designation or topic_id):
        usage_service.search_found_nothing("researchers", q)
    return result


@router.get("/featured", response_model=list[Researcher])
def featured_researchers(
    limit: int = Query(6, ge=1, le=24),
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.featured(limit)


@router.get("/departments", response_model=list[str])
def list_departments(
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.departments()


@router.get("/designations", response_model=list[str])
def list_designations(
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.designations()


@router.get("/academic-ranks", response_model=list[str])
def list_academic_ranks(
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.academic_ranks()


@router.get("/campuses", response_model=list[str])
def list_campuses(
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.campuses()


@router.get(
    "/{researcher_id}/collaborators", response_model=list[CollaborationSuggestion]
)
def researcher_collaborators(
    researcher_id: int,
    sort: str = "relevance",
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.collaborators(researcher_id, sort=sort)


@router.get("/{researcher_id}/export")
def export_publications(
    researcher_id: int,
    format: str = Query("bibtex", pattern="^(bibtex|csv)$"),
    service: ResearcherService = Depends(get_researcher_service),
):
    """A researcher's publication list for a CV, reference manager or file."""
    from app.services import export_service

    person = service.get(researcher_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Researcher not found")
    slug = re.sub(r"[^a-z0-9]+", "-", person.full_name.lower()).strip("-")
    if format == "csv":
        body, kind, ext = export_service.publications_csv(researcher_id), "text/csv", "csv"
    else:
        body, kind, ext = export_service.bibtex(researcher_id), "application/x-bibtex", "bib"
    return Response(
        content=body.encode("utf-8"),
        media_type=f"{kind}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-publications.{ext}"'},
    )


@router.get("/{researcher_id}", response_model=ResearcherDetail)
def get_researcher(
    researcher_id: int,
    service: ResearcherService = Depends(get_researcher_service),
):
    researcher = service.get(researcher_id)
    if researcher is None:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return researcher
