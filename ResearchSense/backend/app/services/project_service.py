"""Business logic for research projects."""
from __future__ import annotations

from app.repositories.base import ProjectRepository
from app.schemas.project import Project


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self._repo = repo

    def list(self, *, status=None) -> list[Project]:
        return self._repo.list(status=status)

    def get(self, project_id: int) -> Project | None:
        return self._repo.get(project_id)
