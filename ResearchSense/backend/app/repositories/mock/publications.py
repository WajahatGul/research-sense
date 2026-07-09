"""JSON-backed PublicationRepository implementation."""
from __future__ import annotations

from app.repositories import loader
from app.repositories.base import PublicationRepository
from app.schemas.publication import Publication


class MockPublicationRepository(PublicationRepository):
    def _all(self) -> list[dict]:
        return loader.load("publications")

    def list(self, *, query=None, year=None, topic_id=None, author_id=None):
        rows = self._all()
        result = []
        for p in rows:
            if query and query.lower() not in p["title"].lower():
                continue
            if year is not None and p["publication_year"] != year:
                continue
            if topic_id is not None and topic_id not in {
                t["topic_id"] for t in p.get("topics", [])
            }:
                continue
            if author_id is not None and not any(
                a.get("researcher_id") == author_id for a in p.get("authors", [])
            ):
                continue
            result.append(Publication(**p))
        result.sort(key=lambda p: p.publication_year, reverse=True)
        return result

    def get(self, publication_id: int) -> Publication | None:
        rec = next(
            (p for p in self._all() if p["publication_id"] == publication_id), None
        )
        return Publication(**rec) if rec else None
