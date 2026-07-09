"""Project endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_project_service
from app.schemas.project import Project
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[Project])
def list_projects(
    status: str | None = None,
    campus: str | None = None,
    service: ProjectService = Depends(get_project_service),
):
    return service.list(status=status, campus=campus)


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: int,
    service: ProjectService = Depends(get_project_service),
):
    project = service.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
