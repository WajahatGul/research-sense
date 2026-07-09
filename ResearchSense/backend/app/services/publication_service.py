"""Business logic for publications."""
from __future__ import annotations

from app.core.pagination import paginate
from app.repositories.base import PublicationRepository
from app.schemas.common import Paginated
from app.schemas.publication import Publication


class PublicationService:
    def __init__(self, repo: PublicationRepository):
        self._repo = repo

    def list(self, *, query=None, year=None, topic_id=None,
             author_id=None, page=1, page_size=10) -> Paginated[Publication]:
        rows = self._repo.list(
            query=query, year=year, topic_id=topic_id, author_id=author_id,
        )
        return paginate(rows, page, page_size)

    def get(self, publication_id: int) -> Publication | None:
        return self._repo.get(publication_id)

    def years(self) -> list[int]:
        rows = self._repo.list()
        return sorted({p.publication_year for p in rows}, reverse=True)
