"""JSON-backed StatsRepository implementation."""

from __future__ import annotations

from app.repositories import loader
from app.repositories.base import StatsRepository
from app.schemas.common import Stats


class MockStatsRepository(StatsRepository):
    def get_stats(self) -> Stats:
        everyone = loader.load("researchers")
        # "researchers" must agree with what the directory shows, or the
        # coverage note contradicts the page under it.
        researchers = [r for r in everyone if not loader.is_extended(r)]
        departments = {r.get("department") for r in researchers if r.get("department")}
        campuses = {r.get("campus") for r in researchers if r.get("campus")}
        return Stats(
            researchers=len(researchers),
            researchers_extended=len(everyone) - len(researchers),
            publications=len(loader.load("publications")),
            projects=len(loader.load("projects")),
            topics=len(loader.load("topics")),
            departments=len(departments),
            campuses=len(campuses),
        )
