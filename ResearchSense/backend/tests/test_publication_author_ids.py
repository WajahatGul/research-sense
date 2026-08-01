"""_publications_for must expose author researcher_ids (Task 8, Fix 4b) so
the frontend can detect "shared paper" without fetching full author objects."""

from unittest.mock import patch

from app.repositories.mock.researchers import MockResearcherRepository


def _pub(pub_id, authors):
    return {
        "publication_id": pub_id,
        "title": "T",
        "publication_year": 2020,
        "journal_name": "J",
        "citation_count": 0,
        "doi": None,
        "authors": authors,
    }


def test_publications_for_includes_known_author_ids_only():
    repo = MockResearcherRepository()
    pubs = [
        _pub(1, [{"researcher_id": 1}, {"researcher_id": 2}, {"researcher_id": None}]),
    ]
    with patch("app.repositories.mock.researchers.loader.load", return_value=pubs):
        result = repo._publications_for(1)
    assert result[0]["author_ids"] == [1, 2]


def test_publications_for_defaults_to_empty_author_ids_when_none_known():
    repo = MockResearcherRepository()
    pubs = [_pub(1, [{"researcher_id": 1}, {"researcher_id": None}])]
    with patch("app.repositories.mock.researchers.loader.load", return_value=pubs):
        result = repo._publications_for(1)
    assert result[0]["author_ids"] == [1]
