"""Aggregate analytics derived from the research data (no extra storage)."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from app.repositories import loader


def _campus_of_researchers() -> dict[int, str]:
    return {r["researcher_id"]: r["campus"] for r in loader.load("researchers")}


class AnalyticsService:
    def overview(self) -> dict:
        researchers = loader.load("researchers")
        publications = loader.load("publications")
        campus_of = _campus_of_researchers()
        campuses = sorted({r["campus"] for r in researchers})

        return {
            "campuses": campuses,
            "publications_per_year": self._per_year_by_campus(publications),
            "citations_per_year": self._citations_per_year(publications),
            "top_venues": self._top_venues(publications),
            "campus_totals": self._campus_totals(researchers, publications),
            "cross_campus_pairs": self._cross_campus(publications, campus_of),
        }

    @staticmethod
    def _per_year_by_campus(publications: list[dict]) -> list[dict]:
        counts: dict[int, Counter] = defaultdict(Counter)
        for p in publications:
            year = p.get("publication_year") or 0
            if year >= 2010:
                counts[year][p.get("campus") or "Unknown"] += 1
        return [
            {"year": year, **counts[year]}
            for year in sorted(counts)
        ]

    @staticmethod
    def _citations_per_year(publications: list[dict]) -> list[dict]:
        totals: Counter = Counter()
        for p in publications:
            year = p.get("publication_year") or 0
            if year >= 2010:
                totals[year] += p.get("citation_count", 0)
        return [{"year": y, "citations": totals[y]} for y in sorted(totals)]

    @staticmethod
    def _top_venues(publications: list[dict], limit: int = 10) -> list[dict]:
        venues = Counter(
            p["journal_name"] for p in publications
            if p.get("journal_name")
            and p["journal_name"] != "Preprint or unindexed venue")
        return [
            {"venue": name, "publications": count}
            for name, count in venues.most_common(limit)
        ]

    @staticmethod
    def _campus_totals(researchers: list[dict],
                       publications: list[dict]) -> list[dict]:
        rows: dict[str, dict] = {}
        for r in researchers:
            row = rows.setdefault(r["campus"], {
                "campus": r["campus"], "researchers": 0,
                "publications": 0, "citations": 0})
            row["researchers"] += 1
        for p in publications:
            row = rows.get(p.get("campus") or "")
            if row:
                row["publications"] += 1
                row["citations"] += p.get("citation_count", 0)
        return sorted(rows.values(), key=lambda r: r["campus"])

    @staticmethod
    def _cross_campus(publications: list[dict],
                      campus_of: dict[int, str]) -> list[dict]:
        """How often authors from two different campuses co-author a paper."""
        pairs: Counter = Counter()
        for p in publications:
            campuses = {
                campus_of[a["researcher_id"]]
                for a in p.get("authors", [])
                if a.get("researcher_id") in campus_of
            }
            for a, b in combinations(sorted(campuses), 2):
                pairs[(a, b)] += 1
        return [
            {"from": a, "to": b, "papers": count}
            for (a, b), count in pairs.most_common()
        ]
