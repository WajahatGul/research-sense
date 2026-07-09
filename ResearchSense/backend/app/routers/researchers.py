"""Researcher endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_researcher_service
from app.schemas.common import Paginated
from app.schemas.researcher import Researcher, ResearcherDetail
from app.services.researcher_service import ResearcherService

router = APIRouter(prefix="/api/researchers", tags=["researchers"])


@router.get("", response_model=Paginated[Researcher])
def list_researchers(
    q: str | None = None,
    department: str | None = None,
    designation: str | None = None,
    topic_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    service: ResearcherService = Depends(get_researcher_service),
):
    return service.list(
        query=q, department=department, designation=designation,
        topic_id=topic_id, page=page, page_size=page_size,
    )


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


@router.get("/{researcher_id}", response_model=ResearcherDetail)
def get_researcher(
    researcher_id: int,
    service: ResearcherService = Depends(get_researcher_service),
):
    researcher = service.get(researcher_id)
    if researcher is None:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return researcher
