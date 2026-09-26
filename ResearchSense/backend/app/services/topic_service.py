"""Business logic for research topics."""

from __future__ import annotations

from app.repositories.base import TopicRepository
from app.schemas.topic import Topic


class TopicService:
    def __init__(self, repo: TopicRepository):
        self._repo = repo

    def list(self, *, query=None, department=None) -> list[Topic]:
        return self._repo.list(query=query, department=department)

    def get(self, topic_id: int) -> Topic | None:
        return self._repo.get(topic_id)
