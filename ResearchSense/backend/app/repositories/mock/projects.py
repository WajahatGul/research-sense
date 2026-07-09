"""JSON-backed ProjectRepository implementation."""
from __future__ import annotations

from app.repositories import loader
from app.repositories.base import ProjectRepository
from app.schemas.project import Project


class MockProjectRepository(ProjectRepository):
    def _all(self) -> list[dict]:
        return loader.load("projects")

    def list(self, *, status=None):
        rows = [
            p for p in self._all()
            if not status or p.get("status") == status
        ]
        rows.sort(key=lambda p: p.get("start_date", ""), reverse=True)
        return [Project(**p) for p in rows]

    def get(self, project_id: int) -> Project | None:
        rec = next((p for p in self._all() if p["project_id"] == project_id), None)
        return Project(**rec) if rec else None
