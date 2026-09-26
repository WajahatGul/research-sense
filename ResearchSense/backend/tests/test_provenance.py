"""A profile's publications say where each record came from."""

from app.repositories.mock.researchers import MockResearcherRepository


def test_profile_publications_carry_their_source():
    repo = MockResearcherRepository()
    person = next(r for r in repo.list() if r.publication_count > 0)
    detail = repo.get(person.researcher_id)
    assert detail.publications
    assert all(p.source for p in detail.publications)
