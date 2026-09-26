"""Business logic for publications."""

from __future__ import annotations

from app.core.pagination import paginate
from app.repositories.base import PublicationRepository
from app.schemas.common import Paginated
from app.schemas.publication import Publication


class PublicationService:
    def __init__(self, repo: PublicationRepository):
        self._repo = repo

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
        page=1,
        page_size=10,
    ) -> Paginated[Publication]:
        filters = dict(
            year=year,
            topic_id=topic_id,
            author_id=author_id,
            campus=campus,
            year_from=year_from,
            year_to=year_to,
            department=department,
            publication_type=publication_type,
            date_from=date_from,
            date_to=date_to,
        )
        rows = self._repo.list(query=query, **filters)
        corrected = None
        if query and not rows:
            corrected = self._repo.suggest(query)
            if corrected:
                rows = self._repo.list(query=corrected, **filters)
        result = paginate(rows, page, page_size)
        if corrected and rows:
            result.corrected_query = corrected
        return result

    def get(self, publication_id: int) -> Publication | None:
        return self._repo.get(publication_id)

    def related(self, publication_id: int, limit: int = 5) -> list[Publication]:
        return self._repo.related(publication_id, limit)

    def years(self) -> list[int]:
        rows = self._repo.list()
        return sorted({p.publication_year for p in rows}, reverse=True)
