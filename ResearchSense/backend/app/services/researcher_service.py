"""Business logic for researchers."""

from __future__ import annotations

from app.core.pagination import paginate
from app.repositories.base import ResearcherRepository
from app.schemas.common import Paginated
from app.schemas.researcher import Researcher, ResearcherDetail


class ResearcherService:
    def __init__(self, repo: ResearcherRepository):
        self._repo = repo

    def list(
        self,
        *,
        query=None,
        campus=None,
        department=None,
        designation=None,
        topic_id=None,
        page=1,
        page_size=12,
    ) -> Paginated[Researcher]:
        filters = dict(
            campus=campus,
            department=department,
            designation=designation,
            topic_id=topic_id,
        )
        rows = self._repo.list(query=query, **filters)
        corrected = None
        # A typo should not read as "we have nobody": retry the closest
        # in-corpus spelling and say so, rather than answering zero.
        if query and not rows:
            corrected = self._repo.suggest(query)
            if corrected:
                rows = self._repo.list(query=corrected, **filters)
        result = paginate(rows, page, page_size)
        if corrected and rows:
            result.corrected_query = corrected
        return result

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

    def academic_ranks(self) -> list[str]:
        return self._repo.academic_ranks()

    def campuses(self) -> list[str]:
        return self._repo.campuses()

    def collaborators(self, researcher_id: int, sort: str = "relevance") -> list[dict]:
        return self._repo.collaborators(researcher_id, sort=sort)
