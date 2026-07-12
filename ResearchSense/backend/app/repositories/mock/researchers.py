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

    def _copublications_with(self, researcher_id: int) -> dict[int, int]:
        """How many publications this researcher co-authored with each other
        Bahria researcher — a proven, mutual collaboration signal."""
        from collections import Counter

        counts: Counter = Counter()
        for p in loader.load("publications"):
            author_ids = [a["researcher_id"] for a in p.get("authors", [])
                          if a.get("researcher_id") is not None]
            if researcher_id in author_ids:
                for other in author_ids:
                    if other != researcher_id:
                        counts[other] += 1
        return dict(counts)

    def _collaborators_for(self, rec: dict) -> list[dict]:
        """Suggest collaborators from two signals:

        1. Past co-authorship — they have already published together (the
           strongest, provably mutual signal).
        2. Shared research areas — overlapping topics suggest a good fit.

        Ranked by co-authored papers first, then number of shared areas, then
        Jaccard overlap. Each suggestion carries the actual shared area names
        and the co-authored-paper count so the recommendation is explainable,
        and the UI can filter by campus or area. Up to 15 are returned; the
        page shows the top ones and lets the user filter.
        """
        rid = rec["researcher_id"]
        my_topics = {t["topic_id"]: t["topic_name"] for t in rec.get("topics", [])}
        my_ids = set(my_topics)
        my_campus = rec.get("campus", "")
        copubs = self._copublications_with(rid)

        scored: list[tuple] = []
        for other in self._all():
            oid = other["researcher_id"]
            if oid == rid:
                continue
            their_ids = {t["topic_id"] for t in other.get("topics", [])}
            shared_ids = my_ids & their_ids
            copub = copubs.get(oid, 0)
            # A candidate needs at least one signal: a shared area or a paper.
            if not shared_ids and copub == 0:
                continue
            shared_names = sorted(my_topics[i] for i in shared_ids)
            union = my_ids | their_ids
            jaccard = len(shared_ids) / max(len(union), 1)
            scored.append((copub, len(shared_ids), jaccard, other, shared_names))
        # Co-authored papers first, then shared-area count, then overlap.
        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
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
                copublications=copub,
                past_coauthor=copub > 0,
                same_campus=(o.get("campus", "") == my_campus),
            ).model_dump()
            for copub, count, jaccard, o, names in scored[:15]
        ]
