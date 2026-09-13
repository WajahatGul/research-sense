"""Extended (publication-only) profiles.

Bahria has ~5,900 publishing authors; the scraped directory has 358, so a
researcher who was not scraped could not find their own work. Every
OpenAlex-affiliated author is now a profile, but one built from the publication
record alone — no department, campus, or biography. Those profiles must stay
findable by name without taking over the pages that assume real directory data.
"""

from __future__ import annotations

import pytest

from app.repositories import loader
from app.repositories.mock.researchers import MockResearcherRepository
from app.repositories.mock.stats import MockStatsRepository
from app.services.analytics_service import AnalyticsService

WS = "extended-test"

CURATED = {
    "researcher_id": 1,
    "full_name": "Nida Aman",
    "designation": "Associate Professor",
    "academic_rank": "Associate Professor",
    "department": "Accounting and Finance",
    "campus": "Islamabad (E-8)",
    "publication_count": 1,
    "citation_count": 5,
    "research_areas": [],
    "topics": [],
    "source": "scraped",
}

EXTENDED = {
    "researcher_id": 2,
    "full_name": "Muhammad Ramzan",
    "designation": "",
    "academic_rank": "",
    "department": "",
    "campus": "",
    "publication_count": 1,
    "citation_count": 3,
    "research_areas": [],
    "topics": [],
    "source": "openalex",
}

PUBS = [
    {
        "publication_id": 1,
        "title": "A curated paper",
        "publication_year": 2021,
        "citation_count": 5,
        "campus": "Islamabad (E-8)",
        "journal_name": "IEEE Access",
        "authors": [{"researcher_id": 1, "full_name": "Nida Aman", "order": 1}],
    },
    {
        "publication_id": 2,
        "title": "An extended paper",
        "publication_year": 2022,
        "citation_count": 3,
        "campus": "",
        "journal_name": "Elsevier",
        "authors": [{"researcher_id": 2, "full_name": "Muhammad Ramzan", "order": 1}],
    },
]


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "WORKSPACES_DIR", tmp_path / "workspaces")
    loader.clear_cache()
    loader.save("researchers", [CURATED, EXTENDED], WS)
    loader.save("publications", PUBS, WS)
    loader.save("topics", [], WS)
    loader.save("projects", [], WS)
    loader.set_workspace(WS)
    yield
    loader.set_workspace(None)
    loader.clear_cache()


def test_browsing_shows_only_directory_profiles():
    """5,000 name-only cards must not bury the real profiles."""
    listed = MockResearcherRepository().list()
    assert [r.full_name for r in listed] == ["Nida Aman"]


def test_searching_by_name_finds_an_extended_author():
    """The whole point: a Bahria author can find their own work."""
    found = MockResearcherRepository().list(query="Ramzan")
    assert [r.full_name for r in found] == ["Muhammad Ramzan"]


def test_an_extended_profile_is_still_readable_directly():
    detail = MockResearcherRepository().get(2)
    assert detail is not None
    assert detail.full_name == "Muhammad Ramzan"


def test_stats_match_what_the_directory_shows():
    stats = MockStatsRepository().get_stats()
    assert stats.researchers == 1  # the curated profile
    assert stats.researchers_extended == 1
    assert stats.publications == 2  # every real paper still counts


def test_campus_analytics_ignore_profiles_that_have_no_campus():
    """Otherwise an 'Unknown' bucket dwarfs every real campus."""
    overview = AnalyticsService().overview()
    assert overview["campuses"] == ["Islamabad (E-8)"]
    totals = {row["campus"]: row for row in overview["campus_totals"]}
    assert set(totals) == {"Islamabad (E-8)"}
    assert totals["Islamabad (E-8)"]["researchers"] == 1
    assert totals["Islamabad (E-8)"]["publications"] == 1


def test_venue_and_citation_charts_still_count_every_paper():
    """Those charts do not depend on where an author sits, so they use all."""
    overview = AnalyticsService().overview()
    venues = {row["venue"] for row in overview["top_venues"]}
    assert {"IEEE Access", "Elsevier"} <= venues
    assert sum(row["citations"] for row in overview["citations_per_year"]) == 8
