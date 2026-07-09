"""JSON-backed ResearcherRepository implementation."""
from __future__ import annotations

from app.repositories import loader
from app.repositories.base import ResearcherRepository
from app.schemas.researcher import (
    CollaborationSuggestion,
    Researcher,
    ResearcherDetail,
)


def _matches(rec: dict, query: str | None, department: str | None,
             designation: str | None, topic_id: int | None) -> bool:
    if query:
        q = query.lower()
        hay = f"{rec['full_name']} {rec.get('designation','')} {rec.get('department','')}".lower()
        if q not in hay:
            return False
    if department and rec.get("department") != department:
        return False
    if designation and rec.get("designation") != designation:
        return False
    if topic_id is not None:
        if topic_id not in {t["topic_id"] for t in rec.get("topics", [])}:
            return False
    return True


class MockResearcherRepository(ResearcherRepository):
    def _all(self) -> list[dict]:
        return loader.load("researchers")

    def list(self, *, query=None, department=None, designation=None, topic_id=None):
        rows = [
            r for r in self._all()
            if _matches(r, query, department, designation, topic_id)
        ]
        rows.sort(key=lambda r: r["full_name"])
        return [Researcher(**r) for r in rows]

    def get(self, researcher_id: int) -> ResearcherDetail | None:
        rec = next(
            (r for r in self._all() if r["researcher_id"] == researcher_id), None
        )
        if rec is None:
            return None
        detail = dict(rec)
        detail["publications"] = self._publications_for(researcher_id)
        detail["collaborators"] = self._collaborators_for(rec)
        return ResearcherDetail(**detail)

    def departments(self) -> list[str]:
        return sorted({r["department"] for r in self._all() if r.get("department")})

    def designations(self) -> list[str]:
        return sorted({r["designation"] for r in self._all() if r.get("designation")})

    def _publications_for(self, researcher_id: int) -> list[dict]:
        pubs = []
        for p in loader.load("publications"):
            if any(a.get("researcher_id") == researcher_id for a in p.get("authors", [])):
                pubs.append({
                    "publication_id": p["publication_id"],
                    "title": p["title"],
                    "publication_year": p["publication_year"],
                    "journal_name": p.get("journal_name", ""),
                    "citation_count": p.get("citation_count", 0),
                })
        pubs.sort(key=lambda p: p["publication_year"], reverse=True)
        return pubs

    def _collaborators_for(self, rec: dict) -> list[dict]:
        my_topics = {t["topic_id"] for t in rec.get("topics", [])}
        scored: list[tuple[float, dict]] = []
        for other in self._all():
            if other["researcher_id"] == rec["researcher_id"]:
                continue
            their = {t["topic_id"] for t in other.get("topics", [])}
            shared = my_topics & their
            if not shared:
                continue
            score = round(len(shared) / max(len(my_topics | their), 1), 2)
            scored.append((score, other))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            CollaborationSuggestion(
                researcher_id=o["researcher_id"],
                full_name=o["full_name"],
                designation=o.get("designation", ""),
                department=o.get("department", ""),
                similarity_score=s,
            ).model_dump()
            for s, o in scored[:4]
        ]
