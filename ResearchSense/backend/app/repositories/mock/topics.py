"""JSON-backed TopicRepository implementation."""

from __future__ import annotations

from app.core.areas import areas_of, paper_areas
from app.core.textsearch import Query
from app.repositories import loader
from app.repositories.base import TopicRepository
from app.schemas.topic import Topic


_counts: dict[tuple[int, int], dict[str, int]] = {}


def _head_counts(topics: list[dict], researchers: list[dict]) -> dict[str, int]:
    """Directory people per area name (see app.core.areas), cached for the
    loaded dataset."""
    key = (id(topics), id(researchers))
    if key not in _counts:
        counts: dict[str, int] = {}
        for r in researchers:
            if r.get("source") == loader.EXTENDED_SOURCE:
                continue
            for name in areas_of(r):
                counts[name] = counts.get(name, 0) + 1
        _counts.clear()
        _counts[key] = counts
    return _counts[key]


def _with_count(t: dict, counts: dict[str, int], papers: dict[int, int]) -> Topic:
    name = " ".join(t["topic_name"].lower().split())
    return Topic(**{**t, "researcher_count": counts.get(name, 0),
                    "publication_count": papers.get(t["topic_id"], 0)})


class MockTopicRepository(TopicRepository):
    def _all(self) -> list[dict]:
        return loader.load("topics")

    def _counts(self) -> dict[str, int]:
        return _head_counts(self._all(), loader.load("researchers"))

    def _papers(self) -> dict[int, int]:
        return paper_areas(self._all(), loader.load("publications"))[1]

    def list(self, *, query=None, department=None, field=None):
        q = Query(query)
        # "What does my department work on?": the areas its faculty list.
        in_department = (
            {
                name
                for r in loader.load("researchers")
                if r.get("department") == department
                for name in areas_of(r)
            }
            if department
            else None
        )
        scored = []
        for t in self._all():
            if in_department is not None and (
                " ".join(t["topic_name"].lower().split()) not in in_department
            ):
                continue
            if field is not None and (t.get("field") or "Other") != field:
                continue
            score = q.score(t["topic_name"]) if q else 0.0
            if score is not None:
                scored.append((score, t))
        counts, papers = self._counts(), self._papers()
        # Closest name first when searching; largest areas first when browsing.
        scored.sort(key=lambda st: (-st[0], -papers.get(st[1]["topic_id"], 0)))
        return [_with_count(t, counts, papers) for _, t in scored]

    def get(self, topic_id: int) -> Topic | None:
        rec = next((t for t in self._all() if t["topic_id"] == topic_id), None)
        return _with_count(rec, self._counts(), self._papers()) if rec else None
