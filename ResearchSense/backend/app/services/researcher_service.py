"""Business logic for researchers."""
from __future__ import annotations

from app.core.pagination import paginate
from app.repositories.base import ResearcherRepository
from app.schemas.common import Paginated
from app.schemas.researcher import Researcher, ResearcherDetail


class ResearcherService:
    def __init__(self, repo: ResearcherRepository):
        self._repo = repo

    def list(self, *, query=None, campus=None, department=None, designation=None,
             topic_id=None, page=1, page_size=12) -> Paginated[Researcher]:
        rows = self._repo.list(
            query=query, campus=campus, department=department,
            designation=designation, topic_id=topic_id,
        )
        return paginate(rows, page, page_size)

    def get(self, researcher_id: int) -> ResearcherDetail | None:
        return self._repo.get(researcher_id)

    def featured(self, limit: int = 6) -> list[Researcher]:
        rows = self._repo.list()
        rows.sort(key=lambda r: r.citation_count, reverse=True)
        return rows[:limit]

    def departments(self) -> list[str]:
        return self._repo.departments()

    def designations(self) -> list[str]:
        return self._repo.designations()

    def campuses(self) -> list[str]:
        return self._repo.campuses()
