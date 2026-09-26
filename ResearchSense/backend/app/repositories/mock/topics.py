"""JSON-backed TopicRepository implementation."""

from __future__ import annotations

from app.core.textsearch import Query
from app.repositories import loader
from app.repositories.base import TopicRepository
from app.schemas.topic import Topic


class MockTopicRepository(TopicRepository):
    def _all(self) -> list[dict]:
        return loader.load("topics")

    def list(self, *, query=None):
        q = Query(query)
        scored = []
        for t in self._all():
            score = q.score(t["topic_name"]) if q else 0.0
            if score is not None:
                scored.append((score, t))
        # Closest name first when searching; largest areas first when browsing.
        scored.sort(key=lambda st: (-st[0], -st[1].get("publication_count", 0)))
        return [Topic(**t) for _, t in scored]

    def get(self, topic_id: int) -> Topic | None:
        rec = next((t for t in self._all() if t["topic_id"] == topic_id), None)
        return Topic(**rec) if rec else None
