"""Business logic for aggregate statistics."""
from __future__ import annotations

from app.repositories.base import StatsRepository
from app.schemas.common import Stats


class StatsService:
    def __init__(self, repo: StatsRepository):
        self._repo = repo

    def get(self) -> Stats:
        return self._repo.get_stats()
