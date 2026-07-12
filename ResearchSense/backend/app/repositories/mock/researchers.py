"""JSON-backed ResearcherRepository implementation."""
from __future__ import annotations

from app.repositories import loader
from app.repositories.base import ResearcherRepository
from app.schemas.researcher import (
    CollaborationSuggestion,
    Researcher,
    ResearcherDetail,
)


def _matches(rec: dict, query: str | None, campus: str | None,
             department: str | None, designation: str | None,
             topic_id: int | None) -> bool:
    if query:
        q = query.lower()
        hay = (f"{rec['full_name']} {rec.get('designation','')} "
               f"{rec.get('department','')} {rec.get('expertise','')}").lower()
        if q not in hay:
            return False
    if campus and rec.get("campus") != campus:
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

    def list(self, *, query=None, campus=None, department=None,
             designation=None, topic_id=None):
        rows = [
            r for r in self._all()
            if _matches(r, query, campus, department, designation, topic_id)
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

    def campuses(self) -> list[str]:
        order = ["Islamabad (E-8)", "Islamabad (H-11)", "Karachi", "Lahore"]
        present = {r["campus"] for r in self._all() if r.get("campus")}
        return [c for c in order if c in present] + sorted(present - set(order))

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
                    "doi": p.get("doi"),
                })
        pubs.sort(key=lambda p: p["publication_year"], reverse=True)
        return pubs

    def _collaborators_for(self, rec: dict) -> list[dict]:
        """Suggest collaborators by shared research areas.

        Ranked by the NUMBER of shared areas first (a concrete, meaningful
        signal), with Jaccard overlap as a tiebreaker. The actual shared area
        names travel with each suggestion so the UI can show why the person is
        recommended instead of a single opaque percentage.
        """
        my_topics = {t["topic_id"]: t["topic_name"] for t in rec.get("topics", [])}
        my_ids = set(my_topics)
        my_campus = rec.get("campus", "")
        scored: list[tuple] = []
        for other in self._all():
            if other["researcher_id"] == rec["researcher_id"]:
                continue
            their_ids = {t["topic_id"] for t in other.get("topics", [])}
            shared_ids = my_ids & their_ids
            if not shared_ids:
                continue
            shared_names = sorted(my_topics[i] for i in shared_ids)
            jaccard = len(shared_ids) / max(len(my_ids | their_ids), 1)
            scored.append((len(shared_ids), jaccard, other, shared_names))
        # More shared areas first; tighter overlap breaks ties.
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [
            CollaborationSuggestion(
                researcher_id=o["researcher_id"],
                full_name=o["full_name"],
                designation=o.get("designation", ""),
                department=o.get("department", ""),
                campus=o.get("campus", ""),
                similarity_score=round(jaccard, 2),
                shared_topics=names,
                shared_count=count,
                same_campus=(o.get("campus", "") == my_campus),
            ).model_dump()
            for count, jaccard, o, names in scored[:6]
        ]
