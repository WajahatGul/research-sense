"""JSON-backed TopicRepository implementation."""
from __future__ import annotations

from app.repositories import loader
from app.repositories.base import TopicRepository
from app.schemas.topic import Topic


class MockTopicRepository(TopicRepository):
    def _all(self) -> list[dict]:
        return loader.load("topics")

    def list(self, *, query=None):
        rows = [
            t for t in self._all()
            if not query or query.lower() in t["topic_name"].lower()
        ]
        rows.sort(key=lambda t: t.get("publication_count", 0), reverse=True)
        return [Topic(**t) for t in rows]

    def get(self, topic_id: int) -> Topic | None:
        rec = next((t for t in self._all() if t["topic_id"] == topic_id), None)
        return Topic(**rec) if rec else None
