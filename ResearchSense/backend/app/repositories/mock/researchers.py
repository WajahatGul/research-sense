"""JSON-backed ResearcherRepository implementation."""

from __future__ import annotations

from app.repositories import loader
from app.repositories.base import ResearcherRepository
from app.schemas.researcher import (
    CollaborationSuggestion,
    Researcher,
    ResearcherDetail,
)
from scripts.normalize import ACADEMIC_RANKS


def score_of(copub: int, shared_ids: set, topic_freq: dict) -> float:
    """Relevance: co-authored papers dominate; shared areas count more when
    they are rare (a shared niche beats a shared 'Machine Learning')."""
    area_score = sum(1.0 / max(topic_freq.get(t, 1), 1) for t in shared_ids)
    return copub * 5.0 + area_score


def _matches(
    rec: dict,
    query: str | None,
    campus: str | None,
    department: str | None,
    designation: str | None,
    topic_id: int | None,
) -> bool:
    if query:
        q = query.lower()
        hay = (
            f"{rec['full_name']} {rec.get('designation', '')} "
            f"{rec.get('department', '')} {rec.get('expertise', '')}"
        ).lower()
        if q not in hay:
            return False
    if campus and rec.get("campus") != campus:
        return False
    if department and rec.get("department") != department:
        return False
    if designation and designation not in (
        rec.get("designation"),
        rec.get("academic_rank"),
    ):
        return False
    return topic_id is None or topic_id in {
        t["topic_id"] for t in rec.get("topics", [])
    }


class MockResearcherRepository(ResearcherRepository):
    def _all(self) -> list[dict]:
        return loader.load("researchers")

    def list(
        self,
        *,
        query=None,
        campus=None,
        department=None,
        designation=None,
        topic_id=None,
    ):
        rows = [
            r
            for r in self._all()
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

    def academic_ranks(self) -> list[str]:
        present = {r["academic_rank"] for r in self._all() if r.get("academic_rank")}
        order = [*ACADEMIC_RANKS, "Other"]
        return [rank for rank in order if rank in present]

    def campuses(self) -> list[str]:
        order = ["Islamabad (E-8)", "Islamabad (H-11)", "Karachi", "Lahore"]
        present = {r["campus"] for r in self._all() if r.get("campus")}
        return [c for c in order if c in present] + sorted(present - set(order))

    def _publications_for(self, researcher_id: int) -> list[dict]:
        pubs = []
        for p in loader.load("publications"):
            if any(
                a.get("researcher_id") == researcher_id for a in p.get("authors", [])
            ):
                pubs.append(
                    {
                        "publication_id": p["publication_id"],
                        "title": p["title"],
                        "publication_year": p["publication_year"],
                        "journal_name": p.get("journal_name", ""),
                        "citation_count": p.get("citation_count", 0),
                        "doi": p.get("doi"),
                        # Author researcher_ids we could resolve (unmatched
                        # authors have researcher_id=None and are dropped).
                        # Lets the frontend detect a shared paper between two
                        # profiles without fetching full author objects.
                        "author_ids": [
                            a["researcher_id"]
                            for a in p.get("authors", [])
                            if a.get("researcher_id") is not None
                        ],
                    }
                )
        pubs.sort(key=lambda p: p["publication_year"], reverse=True)
        return pubs

    def _pubs(self) -> list[dict]:
        return loader.load("publications")

    def _copublications_with(self, researcher_id: int) -> dict[int, int]:
        """How many publications this researcher co-authored with each other
        Bahria researcher — a proven, mutual collaboration signal."""
        from collections import Counter

        counts: Counter = Counter()
        for p in self._pubs():
            author_ids = [
                a["researcher_id"]
                for a in p.get("authors", [])
                if a.get("researcher_id") is not None
            ]
            if researcher_id in author_ids:
                for other in author_ids:
                    if other != researcher_id:
                        counts[other] += 1
        return dict(counts)

    def collaborators(self, researcher_id: int, sort: str = "relevance") -> list[dict]:
        rec = next(
            (r for r in self._all() if r["researcher_id"] == researcher_id), None
        )
        if rec is None:
            return []
        rows = self._collaborators_for(rec)
        keys = {
            "relevance": lambda c: -c["relevance"],
            "shared_areas": lambda c: (-c["shared_count"], -c["relevance"]),
            "coauthored": lambda c: (-c["copublications"], -c["relevance"]),
            "name": lambda c: c["full_name"],
            "campus": lambda c: (c["campus"], -c["relevance"]),
        }
        rows.sort(key=keys.get(sort, keys["relevance"]))
        return rows

    def _collaborators_for(self, rec: dict) -> list[dict]:
        """Suggest collaborators: past co-authors, then researchers sharing
        (rarity-weighted) research areas. No signal -> not suggested (SRS 4).
        Returns at most 12, relevance-ordered."""
        rid = rec["researcher_id"]
        my_topics = {t["topic_id"]: t["topic_name"] for t in rec.get("topics", [])}
        my_ids = set(my_topics)
        my_campus = rec.get("campus", "")
        copubs = self._copublications_with(rid)
        topic_freq: dict[int, int] = {}
        for r in self._all():
            for t in r.get("topics", []):
                topic_freq[t["topic_id"]] = topic_freq.get(t["topic_id"], 0) + 1

        rows: list[dict] = []
        for other in self._all():
            oid = other["researcher_id"]
            if oid == rid:
                continue
            their_ids = {t["topic_id"] for t in other.get("topics", [])}
            shared_ids = my_ids & their_ids
            copub = copubs.get(oid, 0)
            if not shared_ids and copub == 0:
                continue
            shared_names = sorted(my_topics[i] for i in shared_ids)
            union = my_ids | their_ids
            rows.append(
                CollaborationSuggestion(
                    researcher_id=oid,
                    full_name=other["full_name"],
                    designation=other.get("designation", ""),
                    department=other.get("department", ""),
                    campus=other.get("campus", ""),
                    similarity_score=round(len(shared_ids) / max(len(union), 1), 2),
                    shared_topics=shared_names,
                    shared_count=len(shared_ids),
                    copublications=copub,
                    past_coauthor=copub > 0,
                    same_campus=(other.get("campus", "") == my_campus),
                    relevance=round(score_of(copub, shared_ids, topic_freq), 3),
                    # PERSON-level signal, not a fact about THIS pairing: true
                    # when `other` has ever published with an institution
                    # outside Pakistan, anywhere in their record. It does NOT
                    # mean this specific suggested collaboration crosses a
                    # border. Frontend copy must not imply otherwise (Task 8
                    # Fix 1) — a Pakistan-based researcher with one foreign
                    # co-author still gets this badge.
                    international=bool(other.get("international_collaborations")),
                ).model_dump()
            )
        rows.sort(key=lambda c: -c["relevance"])
        return rows[:12]
